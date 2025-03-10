import asyncio
import logging
import time
from datetime import datetime
from main import solana_client, wallet, db, Transaction
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solders.pubkey import Pubkey
from spl.token.client import Token
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Commitment, Finalized
from solana.rpc.api import RPCException
import aiohttp
from prometheus_client import Counter, Gauge, start_http_server

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Metrics setup (Prometheus)
start_http_server(8000)  # Expose metrics on port 8000
METRICS_PREFLIGHT_FAILURES = Counter('solana_preflight_failures_total', 'Total number of preflight failures')
METRICS_TX_SUCCESS = Counter('solana_tx_success_total', 'Total number of successful transactions')
METRICS_TX_FAILURES = Counter('solana_tx_failures_total', 'Total number of failed transactions')
METRICS_RPC_ERRORS = Counter('solana_rpc_errors_total', 'Total number of RPC errors')
METRICS_RATE_LIMIT_DELAY = Gauge('solana_rate_limit_delay_seconds', 'Current delay due to rate limits')

# Constants for retry logic
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 60  # Initial delay in seconds for rate limits
MAX_RETRY_DELAY = 300  # Maximum delay in seconds (5 minutes)
RETRYABLE_RPC_ERRORS = {"429", "Too Many Requests"}  # HTTP status codes or error messages indicating rate limits

async def send_alert(message):
    """Send an alert to an external system (e.g., Slack, email, or logging service)."""
    # This is a placeholder for actual alert integration (e.g., Slack webhook, email, etc.)
    logging.error(f"ALERT: {message}")
    # Example: Send to Slack via webhook
    async with aiohttp.ClientSession() as session:
        webhook_url = "YOUR_SLACK_WEBHOOK_URL"  # Replace with your actual webhook URL
        payload = {"text": message}
        await session.post(webhook_url, json=payload)

async def exponential_backoff(retry_count, base_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY):
    """Calculate exponential backoff delay."""
    delay = min(base_delay * (2 ** retry_count), max_delay)
    METRICS_RATE_LIMIT_DELAY.set(delay)
    logging.info(f"Applying backoff delay of {delay} seconds (retry {retry_count + 1}/{MAX_RETRIES})")
    await asyncio.sleep(delay)

async def create_associated_token_account_manual(solana_client, payer, token_mint):
    """Manually create an associated token account with retry logic."""
    ata = get_associated_token_address(payer.pubkey(), token_mint)
    system_program = Pubkey.from_string("11111111111111111111111111111111")
    rent_sysvar = Pubkey.from_string("SysvarRent111111111111111111111111111111111")

    # Check if the ATA already exists
    account_info = await solana_client.get_account_info(ata)
    if account_info.value is not None:
        logging.info(f"Associated token account {ata} already exists.")
        return ata

    # Instruction to create the ATA
    create_ata_ix = Instruction(
        program_id=ASSOCIATED_TOKEN_PROGRAM_ID,
        accounts=[
            AccountMeta(pubkey=payer.pubkey(), is_signer=True, is_writable=True),  # Payer
            AccountMeta(pubkey=ata, is_signer=False, is_writable=True),  # ATA
            AccountMeta(pubkey=payer.pubkey(), is_signer=False, is_writable=False),  # Wallet (owner)
            AccountMeta(pubkey=token_mint, is_signer=False, is_writable=False),  # Token mint
            AccountMeta(pubkey=system_program, is_signer=False, is_writable=False),  # System program
            AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),  # Token program
            AccountMeta(pubkey=rent_sysvar, is_signer=False, is_writable=False),  # Rent sysvar
        ],
        data=bytes([0])  # Instruction discriminator for create ATA
    )

    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            # Fetch latest blockhash
            blockhash_response = await solana_client.get_latest_blockhash()
            if not blockhash_response.value:
                raise Exception("Failed to fetch latest blockhash")
            blockhash = blockhash_response.value.blockhash

            # Build and send transaction
            message = MessageV0.try_compile(
                payer=payer.pubkey(),
                instructions=[create_ata_ix],
                address_lookup_table_accounts=[],
                recent_blockhash=blockhash
            )
            tx = VersionedTransaction(message, [payer])

            # Send transaction with preflight checks enabled
            tx_response = await solana_client.send_transaction(
                tx,
                opts=TxOpts(
                    skip_preflight=False,  # Enable preflight checks
                    preflight_commitment=Commitment("finalized")  # Maximum certainty
                )
            )
            signature = tx_response.value

            # Confirm the transaction
            await solana_client.confirm_transaction(signature, commitment=Finalized)
            logging.info(f"Created associated token account {ata} with signature: {signature}")
            METRICS_TX_SUCCESS.inc()
            return ata

        except RPCException as e:
            METRICS_RPC_ERRORS.inc()
            error_message = str(e)
            logging.error(f"RPC error creating ATA: {error_message}")
            if any(retryable_error in error_message for retryable_error in RETRYABLE_RPC_ERRORS):
                await exponential_backoff(retry_count)
                retry_count += 1
                continue
            elif "preflight" in error_message.lower():
                METRICS_PREFLIGHT_FAILURES.inc()
                logging.error(f"Preflight failure creating ATA: {error_message}")
                await exponential_backoff(retry_count)
                retry_count += 1
                continue
            else:
                raise  # Non-retryable error, fail immediately

        except Exception as e:
            logging.error(f"Unexpected error creating ATA: {e}", exc_info=True)
            raise

    METRICS_TX_FAILURES.inc()
    error_msg = f"Failed to create ATA after {MAX_RETRIES} retries"
    await send_alert(error_msg)
    raise Exception(error_msg)

async def buy_token(contract_address, group_name):
    try:
        logging.info(f"Attempting to buy token: {contract_address} in {group_name}")
        print(f"Attempting to buy token: {contract_address} in {group_name}")

        # Validate inputs
        if not contract_address:
            raise ValueError("Contract address cannot be empty")
        token_mint = Pubkey.from_string(contract_address)

        # Pump.fun constants (verify these are correct for mainnet-beta)
        pump_fun_program_id = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfH8m3mH6WxsPvaRNW")
        global_account = Pubkey.from_string("4wTV1YmiEkRvAtNtw9NZuPEqXhhX5vEiqWpXhF6bbPSM")
        event_authority = Pubkey.from_string("Ce6TQqeH7tMRFdodFKmDAU6k42nNiHY8RWG9S5RWK6s")
        payer = wallet
        amount_in_sol = 0.01  # 0.01 SOL

        # Validate SOL amount
        if amount_in_sol <= 0:
            raise ValueError("SOL amount must be greater than 0")

        # SOL and token accounts
        sol_mint = Pubkey.from_string("So11111111111111111111111111111111111111112")
        payer_sol_account = get_associated_token_address(payer.pubkey(), sol_mint)
        payer_token_account = get_associated_token_address(payer.pubkey(), token_mint)

        # Bonding curve and associated token account
        bonding_curve = Pubkey.find_program_address(
            [b"bonding-curve", bytes(token_mint)],
            pump_fun_program_id
        )[0]
        bonding_curve_token_account = get_associated_token_address(bonding_curve, token_mint)

        # System accounts
        system_program = Pubkey.from_string("11111111111111111111111111111111")
        rent_sysvar = Pubkey.from_string("SysvarRent111111111111111111111111111111111")

        # Check if payer token account exists; create if not
        account_info = await solana_client.get_account_info(payer_token_account)
        logging.info(f"Account info for {payer_token_account}: {account_info}")
        instructions = []
        if account_info.value is None:
            logging.info(f"Creating token account: {payer_token_account}")
            await create_associated_token_account_manual(solana_client, payer, token_mint)
            logging.info(f"Created token account: {payer_token_account}")
        else:
            logging.info(f"Token account {payer_token_account} already exists")

        # Accounts (verified order)
        accounts = [
            AccountMeta(pubkey=global_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=payer.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(pubkey=token_mint, is_signer=False, is_writable=True),
            AccountMeta(pubkey=bonding_curve, is_signer=False, is_writable=True),
            AccountMeta(pubkey=bonding_curve_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=payer_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=payer_sol_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=sol_mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=system_program, is_signer=False, is_writable=False),
            AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
            AccountMeta(pubkey=ASSOCIATED_TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
            AccountMeta(pubkey=rent_sysvar, is_signer=False, is_writable=False),
            AccountMeta(pubkey=event_authority, is_signer=False, is_writable=False),
            AccountMeta(pubkey=pump_fun_program_id, is_signer=False, is_writable=False),
        ]

        # Instruction data: Correct buy discriminator (verify this is correct)
        amount_in_lamports = int(amount_in_sol * 1_000_000_000)  # 0.01 SOL
        min_tokens_out = 1  # Minimum tokens
        data = (
            bytes.fromhex("eaffb24407acdda9") +
            min_tokens_out.to_bytes(8, byteorder="little") +
            amount_in_lamports.to_bytes(8, byteorder="little")
        )

        # Create buy instruction
        buy_instruction = Instruction(
            program_id=pump_fun_program_id,
            accounts=accounts,
            data=data
        )
        instructions.append(buy_instruction)

        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                # Fetch latest blockhash
                blockhash_response = await solana_client.get_latest_blockhash()
                if not blockhash_response.value:
                    raise Exception("Failed to fetch latest blockhash")
                logging.info(f"Blockhash response: {blockhash_response}")
                blockhash = blockhash_response.value.blockhash

                # Build transaction
                message = MessageV0.try_compile(
                    payer=payer.pubkey(),
                    instructions=instructions,
                    address_lookup_table_accounts=[],
                    recent_blockhash=blockhash
                )
                tx = VersionedTransaction(message, [payer])

                # Debug: Log transaction details
                logging.info(f"Transaction details: program_id={pump_fun_program_id}, accounts={[str(acc.pubkey) for acc in accounts]}, data={data.hex()}")

                # Send transaction with preflight checks enabled
                tx_response = await solana_client.send_transaction(
                    tx,
                    opts=TxOpts(
                        skip_preflight=False,  # Enable preflight checks
                        preflight_commitment=Commitment("finalized")  # Maximum certainty
                    )
                )
                logging.info(f"Transaction response: {tx_response}")
                signature = tx_response.value

                # Confirm the transaction
                await solana_client.confirm_transaction(signature, commitment=Finalized)
                logging.info(f"Buy transaction completed for {contract_address}, signature: {signature}")
                print(f"Buy transaction completed for {contract_address}, signature: {signature}")

                # Record in DB
                with db.session() as session:
                    new_tx = Transaction(
                        token_address=contract_address,
                        transaction_type="buy",
                        amount_in_dollars=1.0,  # Update this to reflect actual dollar amount
                        amount_in_sol=amount_in_sol,
                        status="success",
                        signature=str(signature),
                        timestamp=datetime.now()
                    )
                    session.add(new_tx)
                    session.commit()

                METRICS_TX_SUCCESS.inc()
                return {"token_bought": contract_address, "status": "success", "signature": signature}

            except RPCException as e:
                METRICS_RPC_ERRORS.inc()
                error_message = str(e)
                logging.error(f"RPC error buying token: {error_message}")
                if any(retryable_error in error_message for retryable_error in RETRYABLE_RPC_ERRORS):
                    await exponential_backoff(retry_count)
                    retry_count += 1
                    continue
                elif "preflight" in error_message.lower():
                    METRICS_PREFLIGHT_FAILURES.inc()
                    logging.error(f"Preflight failure buying token: {error_message}")
                    await exponential_backoff(retry_count)
                    retry_count += 1
                    continue
                else:
                    raise  # Non-retryable error, fail immediately

            except Exception as e:
                logging.error(f"Unexpected error buying token: {e}", exc_info=True)
                raise

        METRICS_TX_FAILURES.inc()
        error_msg = f"Failed to buy token {contract_address} after {MAX_RETRIES} retries"
        await send_alert(error_msg)
        raise Exception(error_msg)

    except Exception as e:
        METRICS_TX_FAILURES.inc()
        logging.error(f"Error buying token {contract_address}: {e}", exc_info=True)
        print(f"Error buying token {contract_address}: {e}")

        with db.session() as session:
            new_tx = Transaction(
                token_address=contract_address,
                transaction_type="buy",
                amount_in_dollars=1.0,  # Update this to reflect actual dollar amount
                amount_in_sol=amount_in_sol,
                status="failed",
                error=str(e),
                timestamp=datetime.now()
            )
            session.add(new_tx)
            session.commit()

        raise

# Example usage
if __name__ == "__main__":
    asyncio.run(buy_token("YOUR_CONTRACT_ADDRESS", "YOUR_GROUP_NAME"))
