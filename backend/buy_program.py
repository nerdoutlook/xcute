import logging
from datetime import datetime
import asyncio
import aiohttp
from solders.keypair import Keypair
from solders.transaction import Transaction
from solders.message import Message
from solders.instruction import Instruction, AccountMeta
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from base58 import b58decode
from config import settings as config_settings
from websocket_manager import socketio, db
from models import Contract, Transaction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(config_settings.log_dir / "buy.log"), logging.StreamHandler()],
)

RAYDIUM_PROGRAM_ID = Pubkey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
SYSTEM_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")
WSOL_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")

def load_wallet():
    try:
        if not config_settings.wallet_private_key:
            raise ValueError("Wallet private key is not set in .env file.")
        private_key = b58decode(config_settings.wallet_private_key)
        wallet = Keypair.from_bytes(private_key)
        logging.info(f"Loaded wallet with public key: {wallet.pubkey()}")
        return wallet
    except Exception as e:
        logging.error(f"Error loading wallet: {e}")
        raise

wallet = load_wallet()
solana_client = AsyncClient("https://api.mainnet-beta.solana.com")
active_monitors = set()

def get_ata(wallet_pubkey: Pubkey, mint: Pubkey) -> Pubkey:
    return Pubkey.find_program_address(
        seeds=[bytes(wallet_pubkey), bytes(TOKEN_PROGRAM_ID), bytes(mint)],
        program_id=TOKEN_PROGRAM_ID
    )[0]

def create_ata_instruction(wallet_pubkey: Pubkey, mint: Pubkey) -> Instruction:
    ata = get_ata(wallet_pubkey, mint)
    return Instruction(
        program_id=TOKEN_PROGRAM_ID,
        accounts=[
            AccountMeta(pubkey=wallet_pubkey, is_signer=True, is_writable=True),
            AccountMeta(pubkey=ata, is_signer=False, is_writable=True),
            AccountMeta(pubkey=wallet_pubkey, is_signer=False, is_writable=False),
            AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
            AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        ],
        data=bytes.fromhex("02")
    )

async def get_sol_price() -> float:
    async with aiohttp.ClientSession() as session:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
        async with session.get(url) as response:
            data = await response.json()
            return data["solana"]["usd"]

async def get_token_price_in_sol(token_address: str) -> float:
    pool_info = await fetch_pool_info(token_address)
    pool_account = Pubkey.from_string(pool_info["id"])
    pool_data = (await solana_client.get_account_info(pool_account)).value.data
    base_reserve = 1000000000  # Placeholder
    quote_reserve = 1000000000000  # Placeholder
    return quote_reserve / base_reserve

async def fetch_pool_info(token_address: str):
    async with aiohttp.ClientSession() as session:
        url = "https://api.raydium.io/v2/sdk/liquidity/mainnet.json"
        async with session.get(url) as response:
            data = await response.json()
            for pool in data.get("official", []):
                if pool["baseMint"] == token_address and pool["quoteMint"] == str(WSOL_MINT):
                    return pool
            raise ValueError(f"No SOL/{token_address} pool found")

async def get_fee_estimate() -> int:
    fees = await solana_client.get_recent_prioritization_fees()
    return max(fees.value[0].prioritization_fee, 5000) if fees.value else 5000

async def create_swap_instruction(token_address: str, amount_in_lamports: int, wallet_pubkey: Pubkey, is_buy: bool, slippage_tolerance: float):
    pool_info = await fetch_pool_info(token_address)
    pool_account = Pubkey.from_string(pool_info["id"])
    base_mint = Pubkey.from_string(pool_info["baseMint"])
    quote_mint = Pubkey.from_string(pool_info["quoteMint"])
    base_vault = Pubkey.from_string(pool_info["baseVault"])
    quote_vault = Pubkey.from_string(pool_info["quoteVault"])

    token_account_in = get_ata(wallet_pubkey, quote_mint if is_buy else base_mint)
    token_account_out = get_ata(wallet_pubkey, base_mint if is_buy else quote_mint)
    authority, _ = Pubkey.find_program_address(seeds=[bytes(pool_account)], program_id=RAYDIUM_PROGRAM_ID)

    expected_out = amount_in_lamports if is_buy else (amount_in_lamports * await get_token_price_in_sol(token_address))
    min_amount_out = int(expected_out * (1 - slippage_tolerance))

    accounts = [
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=pool_account, is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority, is_signer=False, is_writable=False),
        AccountMeta(pubkey=wallet_pubkey, is_signer=True, is_writable=True),
        AccountMeta(pubkey=token_account_in, is_signer=False, is_writable=True),
        AccountMeta(pubkey=base_vault, is_signer=False, is_writable=True),
        AccountMeta(pubkey=quote_vault, is_signer=False, is_writable=True),
        AccountMeta(pubkey=token_account_out, is_signer=False, is_writable=True),
        AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]

    data = bytes([9]) + amount_in_lamports.to_bytes(8, "little") + min_amount_out.to_bytes(8, "little")
    return Instruction(program_id=RAYDIUM_PROGRAM_ID, accounts=accounts, data=data)

async def check_wallet_balance(min_sol: float = 0.01):
    balance = (await solana_client.get_balance(wallet.pubkey())).value / 1e9
    if balance < min_sol:
        logging.warning(f"Wallet balance low: {balance} SOL. Please fund with at least {min_sol} SOL.")
    else:
        logging.info(f"Wallet balance: {balance} SOL")
    return balance

async def buy_token(token_address: str, group: str = None):
    try:
        dollar_value = config_settings.BUY_DOLLAR_VALUE
        slippage_tolerance = config_settings.SLIPPAGE_TOLERANCE
        logging.info(f"Attempting to buy token: {token_address} for ${dollar_value}")
        print(f"Starting buy process for {token_address} with ${dollar_value}")

        sol_price = await get_sol_price()
        amount_in_sol = dollar_value / sol_price
        amount_in_lamports = int(amount_in_sol * 1e9)
        fee_estimate = await get_fee_estimate()
        min_lamports_needed = amount_in_lamports + fee_estimate * 3

        balance = (await solana_client.get_balance(wallet.pubkey())).value
        if balance < min_lamports_needed:
            raise ValueError(f"Insufficient balance: {balance / 1e9} SOL available, {(min_lamports_needed / 1e9):.6f} SOL required")

        recent_blockhash = await solana_client.get_latest_blockhash()
        instructions = []

        wsol_ata = get_ata(wallet.pubkey(), WSOL_MINT)
        token_ata = get_ata(wallet.pubkey(), Pubkey.from_string(token_address))
        
        if not (await solana_client.get_account_info(wsol_ata)).value:
            instructions.append(create_ata_instruction(wallet.pubkey(), WSOL_MINT))
            instructions.append(transfer(TransferParams(from_pubkey=wallet.pubkey(), to_pubkey=wsol_ata, lamports=amount_in_lamports)))
        
        if not (await solana_client.get_account_info(token_ata)).value:
            instructions.append(create_ata_instruction(wallet.pubkey(), Pubkey.from_string(token_address)))

        swap_instruction = await create_swap_instruction(token_address, amount_in_lamports, wallet.pubkey(), is_buy=True, slippage_tolerance=slippage_tolerance)
        instructions.append(swap_instruction)

        message = Message.new_with_blockhash(instructions, wallet.pubkey(), recent_blockhash.value.blockhash)
        transaction = Transaction([wallet], message)
        signature = await solana_client.send_transaction(transaction, opts=TxOpts(skip_confirmation=False))
        logging.info(f"Buy transaction sent with signature: {signature.value}")
        print(f"Buy transaction sent: {signature.value}")

        token_amount = await solana_client.get_token_account_balance(token_ata)
        initial_token_amount = token_amount.value.ui_amount
        initial_price = amount_in_sol / initial_token_amount

        buy_details = {
            "token_bought": token_address,
            "dollar_value": dollar_value,
            "amount_in_sol": amount_in_sol,
            "initial_token_amount": initial_token_amount,
            "initial_price": initial_price,
            "slippage_tolerance": slippage_tolerance * 100,
            "wallet_balance_after": (await solana_client.get_balance(wallet.pubkey())).value / 1e9,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        logging.info(f"Buy transaction details: {buy_details}")
        print(f"Buy completed: {buy_details}")

        with db.session.begin():
            # Update contract status to "bought"
            contract = Contract.query.filter_by(address=token_address, group=group).first()
            if contract:
                contract.status = "bought"
                contract.details = str(buy_details)
                print(f"Updated contract {token_address} to status: bought")
            
            # Add transaction
            buy_transaction = Transaction(
                contract_id=contract.id if contract else None,
                token_address=token_address,
                transaction_type="buy",
                amount_in_dollars=dollar_value,
                amount_in_sol=amount_in_sol,
                slippage_tolerance=slippage_tolerance * 100,
                wallet_balance_after=(await solana_client.get_balance(wallet.pubkey())).value / 1e9
            )
            db.session.add(buy_transaction)
            db.session.commit()
            print(f"Added buy transaction to database for {token_address}")

        socketio.emit("buy", buy_details)
        asyncio.create_task(monitor_token_price(token_address, initial_price, initial_token_amount, wallet.pubkey(), slippage_tolerance, contract.id if contract else None))

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error buying token {token_address}: {e}")
        print(f"Buy failed for {token_address}: {e}")
        # Contract already added as "found" in telegram_monitor.py, no further action needed
        raise

async def monitor_token_price(token_address: str, initial_price: float, initial_token_amount: float, wallet_pubkey: Pubkey, slippage_tolerance: float, contract_id: int = None):
    if token_address in active_monitors:
        logging.info(f"Already monitoring {token_address}, skipping duplicate task")
        return
    active_monitors.add(token_address)
    try:
        token_ata = get_ata(wallet_pubkey, Pubkey.from_string(token_address))
        while True:
            current_price = await get_token_price_in_sol(token_address)
            price_change = current_price / initial_price
            logging.info(f"Monitoring {token_address}: Current price {current_price:.8f} SOL, Initial price {initial_price:.8f} SOL, Change {price_change:.2f}x")
            print(f"Monitoring {token_address}: Price change {price_change:.2f}x")

            if price_change >= config_settings.PROFIT_THRESHOLD:
                sell_amount = int(initial_token_amount * config_settings.SELL_PROFIT_FACTOR * 1e9)
                remaining_amount = initial_token_amount * (config_settings.PROFIT_THRESHOLD - config_settings.SELL_PROFIT_FACTOR)
                await sell_token(token_address, sell_amount, wallet_pubkey, slippage_tolerance, contract_id)
                logging.info(f"Sold {config_settings.SELL_PROFIT_FACTOR}x ({sell_amount / 1e9} tokens), holding {remaining_amount} tokens")
                print(f"Sold {sell_amount / 1e9} tokens, holding {remaining_amount}")
                initial_price = current_price
                initial_token_amount = remaining_amount

            elif price_change <= config_settings.LOSS_THRESHOLD:
                sell_amount = (await solana_client.get_token_account_balance(token_ata)).value.amount
                await sell_token(token_address, int(sell_amount), wallet_pubkey, slippage_tolerance, contract_id)
                logging.info(f"Sold all tokens due to price drop below {config_settings.LOSS_THRESHOLD*100}%")
                print(f"Sold all tokens due to {config_settings.LOSS_THRESHOLD*100}% drop")
                break

            await asyncio.sleep(60)

    except Exception as e:
        logging.error(f"Error monitoring token price for {token_address}: {e}")
        print(f"Monitoring error for {token_address}: {e}")
    finally:
        active_monitors.remove(token_address)

async def sell_token(token_address: str, amount_to_sell: int, wallet_pubkey: Pubkey, slippage_tolerance: float, contract_id: int = None):
    try:
        fee_estimate = await get_fee_estimate()
        balance = (await solana_client.get_balance(wallet_pubkey)).value
        if balance < fee_estimate:
            raise ValueError(f"Insufficient SOL for fees: {balance / 1e9} SOL available, {fee_estimate / 1e9} SOL required")

        recent_blockhash = await solana_client.get_latest_blockhash()
        sell_instruction = await create_swap_instruction(token_address, amount_to_sell, wallet_pubkey, is_buy=False, slippage_tolerance=slippage_tolerance)
        
        message = Message.new_with_blockhash([sell_instruction], wallet_pubkey, recent_blockhash.value.blockhash)
        transaction = Transaction([wallet], message)
        signature = await solana_client.send_transaction(transaction, opts=TxOpts(skip_confirmation=False))
        logging.info(f"Sell transaction sent with signature: {signature.value}")
        print(f"Sell transaction sent: {signature.value}")

        sol_received = (amount_to_sell / 1e9) * await get_token_price_in_sol(token_address)
        dollar_value = sol_received * await get_sol_price()

        sell_details = {
            "token_sold": token_address,
            "amount_sold": amount_to_sell / 1e9,
            "amount_in_sol": sol_received,
            "dollar_value": dollar_value,
            "slippage_tolerance": slippage_tolerance * 100,
            "wallet_balance_after": (await solana_client.get_balance(wallet_pubkey)).value / 1e9,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        logging.info(f"Sell transaction details: {sell_details}")
        print(f"Sell completed: {sell_details}")

        with db.session.begin():
            sell_transaction = Transaction(
                contract_id=contract_id,
                token_address=token_address,
                transaction_type="sell",
                amount_in_dollars=dollar_value,
                amount_in_sol=sol_received,
                slippage_tolerance=slippage_tolerance * 100,
                wallet_balance_after=(await solana_client.get_balance(wallet_pubkey)).value / 1e9
            )
            db.session.add(sell_transaction)
            db.session.commit()
            print(f"Added sell transaction to database for {token_address}")

        socketio.emit("sell", sell_details)

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error selling token {token_address}: {e}")
        print(f"Sell failed for {token_address}: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(check_wallet_balance())
