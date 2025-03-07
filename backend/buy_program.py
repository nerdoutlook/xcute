import asyncio
import logging
from datetime import datetime
from main import solana_client, wallet, db, Transaction
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solders.pubkey import Pubkey
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
        amount_in_sol = 0.01  # Example: 0.01 SOL

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

        # Accounts for Pump.fun buy
        accounts = [
            AccountMeta(pubkey=global_account, is_signer=False, is_writable=True),  # 0: Global
            AccountMeta(pubkey=payer, is_signer=True, is_writable=True),  # 1: Payer
            AccountMeta(pubkey=token_mint, is_signer=False, is_writable=True),  # 2: Token mint
            AccountMeta(pubkey=bonding_curve, is_signer=False, is_writable=True),  # 3: Bonding curve
            AccountMeta(pubkey=bonding_curve_token_account, is_signer=False, is_writable=True),  # 4: Bonding curve token account
            AccountMeta(pubkey=payer_token_account, is_signer=False, is_writable=True),  # 5: Payer token account
            AccountMeta(pubkey=payer_sol_account, is_signer=False, is_writable=True),  # 6: Payer SOL account
            AccountMeta(pubkey=sol_mint, is_signer=False, is_writable=False),  # 7: SOL mint
            AccountMeta(pubkey=system_program, is_signer=False, is_writable=False),  # 8: System program
            AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),  # 9: Token program
            AccountMeta(pubkey=ASSOCIATED_TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),  # 10: Associated token program
            AccountMeta(pubkey=rent_sysvar, is_signer=False, is_writable=False),  # 11: Rent sysvar
            AccountMeta(pubkey=event_authority, is_signer=False, is_writable=False),  # 12: Event authority
            AccountMeta(pubkey=pump_fun_program_id, is_signer=False, is_writable=False),  # 13: Program ID (for events)
        ]

        # Instruction data: Buy instruction (discriminator 0) + amount + max SOL cost
        amount_in_lamports = int(amount_in_sol * 1_000_000_000)  # 0.01 SOL in lamports
        max_sol_cost = int(0.015 * 1_000_000_000)  # Example: max 0.015 SOL
        data = (
            bytes([0]) +  # Discriminator for buy (0)
            amount_in_lamports.to_bytes(8, byteorder="little") +  # Amount to spend
            max_sol_cost.to_bytes(8, byteorder="little")  # Max SOL cost
        )

        # Create instruction
        instruction = Instruction(
            program_id=pump_fun_program_id,
            accounts=accounts,
            data=data
        )

        # Build and send transaction
        blockhash = (await solana_client.get_latest_blockhash()).value.blockhash
        message = MessageV0.try_compile(
            payer=payer,
            instructions=[instruction],
            address_lookup_table_accounts=[],
            recent_blockhash=blockhash
        )
        tx = VersionedTransaction(message, [wallet])
        signature = (await solana_client.send_transaction(tx)).value

        logging.info(f"Buy transaction completed for {contract_address}, signature: {signature}")
        print(f"Buy transaction completed for {contract_address}, signature: {signature}")

        # Record in DB
        with db.session() as session:
            new_tx = Transaction(
                token_address=contract_address,
                transaction_type="buy",
                amount_in_dollars=1.0,  # Adjust as needed
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
