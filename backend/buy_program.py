import logging
from datetime import datetime
from solders.keypair import Keypair
from solders.transaction import Transaction
from solders.message import Message
from solders.hash import Hash
from solders.instruction import Instruction, AccountMeta
from solders.pubkey import Pubkey
from solders.signature import Signature
from solana.rpc.async_api import AsyncClient
from base58 import b58decode
from config import settings
from websocket_manager import socketio, db, Transaction
from dotenv import load_dotenv

load_dotenv()

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.log_dir / "buy.log"),
        logging.StreamHandler()
    ],
)

# Load the wallet from the private key in .env
def load_wallet():
    try:
        if not settings.wallet_private_key:
            raise ValueError("Wallet private key is not set in .env file.")
        
        private_key = b58decode(settings.wallet_private_key)
        wallet = Keypair.from_bytes(private_key)
        logging.info(f"Loaded wallet with public key: {wallet.pubkey()}")
    except Exception as e:
        logging.error(f"Error loading wallet: {e}")
        raise
    return wallet

wallet = load_wallet()

# Initialize Solana RPC client (Main-net)
solana_client = AsyncClient("https://api.mainnet-beta.solana.com")

# Fetch the current price of a token in USD (replace with actual API call)
async def get_token_price(token_address: str) -> float:
    return 0.01  # Example: $0.01 per token

# Fetch a recent blockhash
async def get_recent_blockhash():
    response = await solana_client.get_latest_blockhash()
    return response.value.blockhash

# Create Raydium swap instructions
def create_raydium_swap_instructions(
    token_address: str,
    amount_in_sol: float,
    wallet_pubkey: Pubkey
):
    raydium_swap_program_id = Pubkey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")
    token_account_in = Pubkey.default()  # SOL account
    token_account_out = Pubkey.default()  # Token account
    pool_account = Pubkey.default()  # Raydium pool account
    authority = Pubkey.default()  # Authority account

    accounts = [
        AccountMeta(pubkey=token_account_in, is_signer=False, is_writable=True),
        AccountMeta(pubkey=token_account_out, is_signer=False, is_writable=True),
        AccountMeta(pubkey=pool_account, is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority, is_signer=False, is_writable=False),
        AccountMeta(pubkey=wallet_pubkey, is_signer=True, is_writable=True),
    ]

    data = bytes([1])  # Example: Swap instruction
    swap_instruction = Instruction(
        program_id=raydium_swap_program_id,
        accounts=accounts,
        data=data,
    )
    return swap_instruction

'''
async def buy_token(token_address: str):
    try:
        logging.info(f"Attempting to buy token: {token_address}")

        # Step 1: Get the token price in USD
        token_price = await get_token_price(token_address)
        if token_price <= 0:
            raise ValueError("Invalid token price")

        # Step 2: Calculate the amount of tokens to buy based on dollar value
        dollar_value = 1  # Example: $1 worth of tokens
        amount_in_tokens = dollar_value / token_price
        logging.info(f"Buying {amount_in_tokens} tokens (${dollar_value} worth)")

        # Step 3: Get a recent blockhash
        recent_blockhash = await get_recent_blockhash()

        # Step 4: Create Raydium swap instructions
        amount_in_sol = dollar_value  # Example: Assume 1 SOL = $100
        swap_instruction = create_raydium_swap_instructions(
            token_address, amount_in_sol, wallet.pubkey()
        )

        # Step 5: Create the transaction message
        message = Message([swap_instruction])  # Create a Message object

        # Step 6: Create the transaction
        transaction = Transaction.new_unsigned(message)  # Create an unsigned transaction

        # Step 7: Sign the transaction
        transaction.sign([wallet], recent_blockhash)  # Sign the transaction with the wallet

        # Step 8: Send the transaction
        signature = await solana_client.send_transaction(transaction)
        logging.info(f"Transaction sent with signature: {signature}")

        # Step 9: Log the buy transaction
        buy_details = {
            "token_bought": token_address,
            "amount_bought": dollar_value,  # Dollar value of tokens bought
            "slippage_paid": 0.5,  # Example: 0.5% slippage
            "wallet_balance_after": await solana_client.get_balance(wallet.pubkey()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        logging.info(f"Buy transaction details: {buy_details}")

        # Step 10: Broadcast buy transaction data to WebSocket clients
        socketio.emit("buy", buy_details)
    except Exception as e:
        logging.error(f"Error buying token: {e}")
'''

async def buy_token(token_address: str):
    try:
        logging.info(f"Attempting to buy token: {token_address}")

        # Step 1: Get the token price in USD
        token_price = await get_token_price(token_address)
        if token_price <= 0:
            raise ValueError("Invalid token price")

        # Step 2: Calculate the amount of tokens to buy based on dollar value
        dollar_value = 1  # Example: $1 worth of tokens
        amount_in_tokens = dollar_value / token_price
        logging.info(f"Buying {amount_in_tokens} tokens (${dollar_value} worth)")

        # Step 3: Get a recent blockhash
        recent_blockhash = await get_recent_blockhash()

        # Step 4: Create Raydium swap instructions
        amount_in_sol = dollar_value  # Example: Assume 1 SOL = $100
        swap_instruction = create_raydium_swap_instructions(
            token_address, amount_in_sol, wallet.pubkey()
        )

        # Step 5: Create the transaction message
        message = Message.new_with_blockhash(
            [swap_instruction],  # List of instructions
            payer=wallet.pubkey(),  # Payer's public key
            blockhash=recent_blockhash,  # Recent blockhash
        )

        # Step 6: Create the transaction
        transaction = Transaction.new_unsigned(message)  # Create an unsigned transaction

        # Step 7: Sign the transaction
        transaction.sign([wallet], recent_blockhash)  # Sign the transaction with the wallet

        # Step 8: Send the transaction
        signature = await solana_client.send_transaction(transaction)
        logging.info(f"Transaction sent with signature: {signature}")

        # Step 9: Log the buy transaction
        buy_details = {
            "token_bought": token_address,
            "amount_bought": dollar_value,  # Dollar value of tokens bought
            "slippage_paid": 0.5,  # Example: 0.5% slippage
            "wallet_balance_after": await solana_client.get_balance(wallet.pubkey()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        logging.info(f"Buy transaction details: {buy_details}")

        # Step 10: Broadcast buy transaction data to WebSocket clients
        socketio.emit("buy", buy_details)
    except Exception as e:
        logging.error(f"Error buying token: {e}")
