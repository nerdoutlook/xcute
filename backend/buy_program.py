import asyncio
import logging
from datetime import datetime
from main import solana_client, wallet, db, Transaction
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solders.pubkey import Pubkey
from spl.token.client import Token
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address
from solana.rpc.types import TxOpts, Commitment
from solana.rpc.core import RPCException
from solana.exceptions import SolanaRpcException

async def create_associated_token_account_manual(solana_client, payer, token_mint, blockhash):
    """Manually create an associated token account with retry and single confirmation."""
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
            AccountMeta(pubkey=payer.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(pubkey=ata, is_signer=False, is_writable=True),
            AccountMeta(pubkey=payer.pubkey(), is_signer=False, is_writable=False),
            AccountMeta(pubkey=token_mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=system_program, is_signer=False, is_writable=False),
            AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
            AccountMeta(pubkey=rent_sysvar, is_signer=False, is_writable=False),
        ],
        data=bytes([0])
    )

    # Use provided blockhash
    message = MessageV0.try_compile(
        payer=payer.pubkey(),
        instructions=[create_ata_ix],
        address_lookup_table_accounts=[],
        recent_blockhash=blockhash
    )
    tx = VersionedTransaction(message, [payer])

    # Send with retries
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            tx_response = await solana_client.send_transaction(tx, opts=TxOpts(skip_preflight=True))
            signature = tx_response.value
            logging.info(f"ATA creation sent with signature: {signature}")

            # Single confirmation check after a short delay
            await asyncio.sleep(2)  # Wait 2s for propagation
            confirmation = await solana_client.get_signature_statuses([signature])
            status = confirmation.value[0]
            if status and status.confirmation_status == Commitment("finalized"):
                logging.info(f"ATA creation confirmed with signature: {signature}")
                return ata
            else:
                raise Exception(f"ATA creation transaction {signature} not finalized")
        except SolanaRpcException as e:
            if "429" in str(e):
                wait_time = 2 ** attempt
                logging.warning(f"Rate limit hit on attempt {attempt + 1}/{max_attempts}. Waiting {wait_time}s.")
                await asyncio.sleep(wait_time)
            else:
                raise
    raise Exception(f"Failed to create ATA for {token_mint} after {max_attempts} attempts")

async def buy_token(contract_address, group_name):
    try:
        logging.info(f"Attempting to buy token: {contract_address} in {group_name}")
        print(f"Attempting to buy token: {contract_address} in {group_name}")

        # Pump.fun constants
        pump_fun_program_id = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfH8m3mH6WxsPvaRNW")
        global_account = Pubkey.from_string("4wTV1YmiEkRvAtNtw9NZuPEqXhhX5vEiqWpXhF6bbPSM")
        event_authority = Pubkey.from_string("Ce6TQqeH7tMRFdodFKmDAU6k42nNiHY8RWG9S5RWK6s")
        token_mint = Pubkey.from_string(contract_address)
        payer = wallet
        amount_in_sol = 0.01  # 0.01 SOL

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

        # Single blockhash for both transactions
        blockhash_response = await solana_client.get_latest_blockhash()
        blockhash = blockhash_response.value.blockhash
        logging.info(f"Using blockhash: {blockhash}")

        # Check and create ATA if needed
        account_info = await solana_client.get_account_info(payer_token_account)
        logging.info(f"Account info for {payer_token_account}: {account_info}")
        instructions = []
        if account_info.value is None:
            logging.info(f"Creating token account: {payer_token_account}")
            await create_associated_token_account_manual(solana_client, payer, token_mint, blockhash)
            logging.info(f"Created token account: {payer_token_account}")
        else:
            logging.info(f"Token account {payer_token_account} already exists")

        # Buy instruction
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

        amount_in_lamports = int(amount_in_sol * 1_000_000_000)  # 0.01 SOL
        min_tokens_out = 1
        data = (
            bytes.fromhex("eaffb24407acdda9") +
            min_tokens_out.to_bytes(8, byteorder="little") +
            amount_in_lamports.to_bytes(8, byteorder="little")
        )

        buy_instruction = Instruction(
            program_id=pump_fun_program_id,
            accounts=accounts,
            data=data
        )
        instructions.append(buy_instruction)

        # Build and send buy transaction with cached blockhash
        message = MessageV0.try_compile(
            payer=payer.pubkey(),
            instructions=instructions,
            address_lookup_table_accounts=[],
            recent_blockhash=blockhash
        )
        tx = VersionedTransaction(message, [payer])

        logging.info(f"Transaction details: program_id={pump_fun_program_id}, accounts={[str(acc.pubkey) for acc in accounts]}, data={data.hex()}")

        # Send and confirm with retries
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                tx_response = await solana_client.send_transaction(tx, opts=TxOpts(skip_preflight=True))
                signature = tx_response.value
                logging.info(f"Transaction sent with signature: {signature}")

                # Single confirmation check
                await asyncio.sleep(2)
                confirmation = await solana_client.get_signature_statuses([signature])
                status = confirmation.value[0]
                if status and status.confirmation_status == Commitment("finalized"):
                    logging.info(f"Buy transaction confirmed with signature: {signature}")
                    print(f"Buy transaction completed for {contract_address}, signature: {signature}")

                    # Record in DB
                    with db.session() as session:
                        new_tx = Transaction(
                            token_address=contract_address,
                            transaction_type="buy",
                            amount_in_dollars=1.0,
                            amount_in_sol=amount_in_sol,
                            status="success",
                            signature=str(signature),
                            timestamp=datetime.now()
                        )
                        session.add(new_tx)
                        session.commit()

                    return {"token_bought": contract_address, "status": "success", "signature": signature}
                else:
                    raise Exception(f"Transaction {signature} not finalized")
            except SolanaRpcException as e:
                if "429" in str(e):
                    wait_time = 2 ** attempt
                    logging.warning(f"Rate limit hit on attempt {attempt + 1}/{max_attempts}. Waiting {wait_time}s.")
                    await asyncio.sleep(wait_time)
                else:
                    if "ProgramAccountNotFound" in str(e):
                        logging.error(f"Pump.fun program not found for token {contract_address}. Invalid Pump.fun token?")
                    raise
        raise Exception(f"Failed to buy token {contract_address} after {max_attempts} attempts")

    except Exception as e:
        logging.error(f"Error buying token {contract_address}: {e}", exc_info=True)
        print(f"Error buying token {contract_address}: {e}")

        with db.session() as session:
            new_tx = Transaction(
                token_address=contract_address,
                transaction_type="buy",
                amount_in_dollars=1.0,
                amount_in_sol=0.0,
                status="failed",
                error=str(e),
                timestamp=datetime.now()
            )
            session.add(new_tx)
            session.commit()

        raise
