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

async def buy_token(contract_address, group_name):
    try:
        logging.info(f"Attempting to buy token: {contract_address} in {group_name}")
        print(f"Attempting to buy token: {contract_address} in {group_name}")

        # Pump.fun constants
        pump_fun_program_id = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfH8m3mH6WxsPvaRNW")
        global_account = Pubkey.from_string("4wTV1YmiEkRvAtNtw9NZuPEqXhhX5vEiqWpXhF6bbPSM")
        event_authority = Pubkey.from_string("Ce6TQqeH7tMRFdodFKmDAU6k42nNiHY8RWG9S5RWK6s")
        token_mint = Pubkey.from_string(contract_address)
        payer = wallet.pubkey()
        amount_in_sol = 0.01  # 0.01 SOL

        # SOL and token accounts
        sol_mint = Pubkey.from_string("So11111111111111111111111111111111111111112")
        payer_sol_account = get_associated_token_address(payer, sol_mint)
        payer_token_account = get_associated_token_address(payer, token_mint)

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
            token_client = Token(solana_client, token_mint, TOKEN_PROGRAM_ID, wallet)
            await token_client.create_associated_token_account(payer)
            logging.info(f"Created token account: {payer_token_account}")
        else:
            logging.info(f"Token account {payer_token_account} already exists")

        # Accounts (verified order)
        accounts = [
            AccountMeta(pubkey=global_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=payer, is_signer=True, is_writable=True),
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

        # Instruction data: Correct buy discriminator
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

        # Build and send transaction
        blockhash_response = await solana_client.get_latest_blockhash()
        logging.info(f"Blockhash response: {blockhash_response}")
        blockhash = blockhash_response.value.blockhash
        message = MessageV0.try_compile(
            payer=payer,
            instructions=instructions,
            address_lookup_table_accounts=[],
            recent_blockhash=blockhash
        )
        tx = VersionedTransaction(message, [wallet])

        # Debug: Log transaction details
        logging.info(f"Transaction details: program_id={pump_fun_program_id}, accounts={[str(acc.pubkey) for acc in accounts]}, data={data.hex()}")

        tx_response = await solana_client.send_transaction(tx)
        logging.info(f"Transaction response: {tx_response}")
        signature = tx_response.value  # Adjust if logs show a different structure

        logging.info(f"Buy transaction completed for {contract_address}, signature: {signature}")
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
