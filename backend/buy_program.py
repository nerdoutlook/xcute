import asyncio
import logging
import struct
from datetime import datetime
from main import solana_client, wallet, db, Transaction
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solders.pubkey import Pubkey
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address, create_associated_token_account

async def buy_token(contract_address, group_name):
    try:
        logging.info(f"Attempting to buy token: {contract_address} in {group_name}")
        print(f"Attempting to buy token: {contract_address} in {group_name}")

        # Pump.fun constants
        pump_fun_program_id = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfH8m3mH6WxsPvaRNW")
        global_account = Pubkey.from_string("4wTV1YmiEkRvAtNtw9NZuPEqXhhX5vEiqWpXhF6bbPSM")
        fee_recipient = Pubkey.from_string("CebN5WGQ4jvKTPtTangStie375uDF1dVtaudpGZaJmvA")
        event_authority = Pubkey.from_string("Ce6TQqeH7tMRFdodFKmDAU6k42nNiHY8RWG9S5RWK6s")
        token_mint = Pubkey.from_string(contract_address)
        payer = wallet.pubkey()
        amount_in_sol = 0.01  # 0.01 SOL
        slippage = 5  # 5% slippage

        # Bonding curve and associated token account
        bonding_curve = Pubkey.find_program_address(
            [b"bonding-curve", bytes(token_mint)],
            pump_fun_program_id
        )[0]
        associated_bonding_curve = get_associated_token_address(bonding_curve, token_mint)
        associated_user = get_associated_token_address(payer, token_mint)

        # System accounts
        system_program = Pubkey.from_string("11111111111111111111111111111111")
        rent_sysvar = Pubkey.from_string("SysvarRent111111111111111111111111111111111")

        # Check/create token account
        token_account_instruction = None
        try:
            account_info = await solana_client.get_token_accounts_by_owner(payer, token_mint)
            if not account_info.value:
                token_account_instruction = create_associated_token_account(payer, payer, token_mint)
                logging.info(f"Creating token account: {associated_user}")
            else:
                logging.info(f"Token account found: {associated_user}")
        except Exception as e:
            logging.warning(f"Token account check failed, creating new: {e}")
            token_account_instruction = create_associated_token_account(payer, payer, token_mint)

        # Calculate amounts
        sol_dec = 1_000_000_000  # 1 SOL in lamports
        amount_in_lamports = int(amount_in_sol * sol_dec)
        max_sol_cost = int(amount_in_lamports * (1 + slippage / 100))  # Slippage adjustment
        min_tokens_out = 1  # Minimum tokens (avoid 0)

        # Instruction data
        data = bytearray()
        data.extend(bytes.fromhex("66063d1201daebea"))  # Buy discriminator
        data.extend(struct.pack('<Q', min_tokens_out))  # Min tokens out
        data.extend(struct.pack('<Q', max_sol_cost))  # Max SOL cost

        # Accounts (12, aligned with pump_fun_py)
        accounts = [
            AccountMeta(pubkey=global_account, is_signer=False, is_writable=False),  # 0: Global
            AccountMeta(pubkey=fee_recipient, is_signer=False, is_writable=True),  # 1: Fee recipient
            AccountMeta(pubkey=token_mint, is_signer=False, is_writable=False),  # 2: Mint
            AccountMeta(pubkey=bonding_curve, is_signer=False, is_writable=True),  # 3: Bonding curve
            AccountMeta(pubkey=associated_bonding_curve, is_signer=False, is_writable=True),  # 4: Bonding curve ATA
            AccountMeta(pubkey=associated_user, is_signer=False, is_writable=True),  # 5: User ATA
            AccountMeta(pubkey=payer, is_signer=True, is_writable=True),  # 6: User
            AccountMeta(pubkey=system_program, is_signer=False, is_writable=False),  # 7: System program
            AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),  # 8: Token program
            AccountMeta(pubkey=rent_sysvar, is_signer=False, is_writable=False),  # 9: Rent sysvar
            AccountMeta(pubkey=event_authority, is_signer=False, is_writable=False),  # 10: Event authority
            AccountMeta(pubkey=pump_fun_program_id, is_signer=False, is_writable=False),  # 11: Program ID
        ]

        # Instructions
        instructions = [
            set_compute_unit_limit(300_000),  # Default compute budget
            set_compute_unit_price(100_000),  # 0.1 lamports per CU
        ]
        if token_account_instruction:
            instructions.append(token_account_instruction)
        instructions.append(Instruction(
            program_id=pump_fun_program_id,
            accounts=accounts,
            data=bytes(data)
        ))

        # Build and send transaction
        blockhash = (await solana_client.get_latest_blockhash()).value.blockhash
        message = MessageV0.try_compile(
            payer=payer,
            instructions=instructions,
            address_lookup_table_accounts=[],
            recent_blockhash=blockhash
        )
        tx = VersionedTransaction(message, [wallet])

        # Debug: Log transaction details
        logging.info(f"Transaction details: program_id={pump_fun_program_id}, accounts={[str(acc.pubkey) for acc in accounts]}, data={data.hex()}")

        # Send transaction
        signature = (await solana_client.send_transaction(tx)).value

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
