import asyncio
import logging
from datetime import datetime
from main import solana_client, wallet, db, Transaction
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address

async def buy_token(contract_address, group_name):
    try:
        logging.info(f"Attempting to buy token: {contract_address} in {group_name}")
        print(f"Attempting to buy token: {contract_address} in {group_name}")

        # Pump.fun program ID
        pump_fun_program_id = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfH8m3mH6WxsPvaRNW")
        token_mint = Pubkey.from_string(contract_address)
        payer = wallet.pubkey()
        amount_in_sol = 0.01  # Example: 0.01 SOL

        # SOL mint and wallet's SOL token account (for payment)
        sol_mint = Pubkey.from_string("So11111111111111111111111111111111111111112")  # Wrapped SOL
        payer_sol_account = get_associated_token_address(payer, sol_mint)

        # Token account for the new token (to receive)
        payer_token_account = get_associated_token_address(payer, token_mint)

        # Placeholder accounts (adjust based on Pump.fun's buy instruction)
        accounts = [
            AccountMeta(pubkey=payer, is_signer=True, is_writable=True),  # Payer (wallet)
            AccountMeta(pubkey=payer_sol_account, is_signer=False, is_writable=True),  # SOL account
            AccountMeta(pubkey=payer_token_account, is_signer=False, is_writable=True),  # Token account
            AccountMeta(pubkey=token_mint, is_signer=False, is_writable=False),  # Token mint
            AccountMeta(pubkey=sol_mint, is_signer=False, is_writable=False),  # SOL mint
            AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),  # Token program
            AccountMeta(pubkey=ASSOCIATED_TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),  # Associated token program
            AccountMeta(pubkey=Pubkey.from_string("11111111111111111111111111111111"), is_signer=False, is_writable=False),  # System program
            # Add Pump.fun-specific accounts (e.g., bonding curve, pool) as needed
        ]

        # Placeholder data: encode amount (adjust based on Pump.fun's instruction format)
        amount_in_lamports = int(amount_in_sol * 1_000_000_000)  # Convert SOL to lamports
        data = bytes([1]) + amount_in_lamports.to_bytes(8, byteorder="little")  # Example: instruction discriminator + amount

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

        # Log success
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
        
        # Record failure in DB
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

if __name__ == "__main__":
    # For testing locally (adjust wallet and solana_client setup)
    asyncio.run(buy_token("HGxJRGD6RBvnb2mQN2QH4XmJtYQLKgBd2aNfuiqNpump", "TestGroup"))
