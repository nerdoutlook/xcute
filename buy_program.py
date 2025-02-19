import logging
from datetime import datetime
from solders.keypair import Keypair  # For wallet/keypair
from solders.transaction import Transaction  # For creating transactions
from solders.message import Message  # For transaction message
from solders.hash import Hash  # For recent blockhash
from solders.instruction import Instruction, AccountMeta  # For transaction instructions
from solders.pubkey import Pubkey  # For public keys
from solders.signature import Signature  # For transaction signatures
from solana.rpc.async_api import AsyncClient  # For Solana RPC
from base58 import b58decode  # For decoding private keys
from config import settings
from websocket_manager import socketio

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
        # Decode the private key from base58
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
    # Placeholder: Replace with actual API call to fetch token price
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
    # Raydium swap program ID (Devnet)
    raydium_swap_program_id = Pubkey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")

    # Token accounts and other required accounts
    # Replace with actual accounts for the swap
    token_account_in = Pubkey.default()  # SOL account
    token_account_out = Pubkey.default()  # Token account
    pool_account = Pubkey.default()  # Raydium pool account
    authority = Pubkey.default()  # Authority account

    # Convert Pubkey objects to AccountMeta
    accounts = [
        AccountMeta(pubkey=token_account_in, is_signer=False, is_writable=True),
        AccountMeta(pubkey=token_account_out, is_signer=False, is_writable=True),
        AccountMeta(pubkey=pool_account, is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority, is_signer=False, is_writable=False),
        AccountMeta(pubkey=wallet_pubkey, is_signer=True, is_writable=True),
    ]

    # Instruction data (replace with actual swap data)
    data = bytes([1])  # Example: Swap instruction

    # Create the swap instruction
    swap_instruction = Instruction(
        program_id=raydium_swap_program_id,
        accounts=accounts,
        data=data,
    )
    return swap_instruction

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
        message = Message([swap_instruction])

        # Step 6: Create the transaction
        transaction = Transaction(
            message=message,
            from_keypairs=[wallet],
            recent_blockhash=recent_blockhash,
        )

        # Step 7: Send the transaction
        signature = await solana_client.send_transaction(transaction)
        logging.info(f"Transaction sent with signature: {signature}")

        # Step 8: Log the buy transaction
        buy_details = {
            "token_bought": token_address,
            "amount_bought": dollar_value,  # Dollar value of tokens bought
            "slippage_paid": 0.5,  # Example: 0.5% slippage
            "wallet_balance_after": await solana_client.get_balance(wallet.pubkey()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        logging.info(f"Buy transaction details: {buy_details}")

        # Step 9: Broadcast buy transaction data to WebSocket clients
        socketio.emit("buy", buy_details)
    except Exception as e:
        logging.error(f"Error buying token: {e}")
