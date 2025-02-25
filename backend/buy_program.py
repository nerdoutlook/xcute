import asyncio
import logging
import os
from datetime import datetime
import aiohttp
from solders.transaction import Transaction
from solders.message import Message
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.keypair import Keypair
from solders.rpc.async_api import AsynClient
#from solana.rpc.async_api import AsyncClient
#from solana.rpc.types import TxOpts
from solders.rpc.types import Tx0pts
from config import settings as config_settings
from websocket_manager import socketio, db
from models import Transaction, Contract
from spl.token.instructions import create_associated_token_account

# Constants
WSOL_MINT = Pubkey.from_string('So11111111111111111111111111111111111111112')
RAYDIUM_AUTHORITY = Pubkey.from_string('5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVnc2dA9GZwXJD')
RAYDIUM_POOL = Pubkey.from_string('675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8')
FEE_DESTINATION = Pubkey.from_string('7YttLkHDoqupeaZiLn99yYZSL3oQ6xxyUcZFKxkyTig1')

# Initialize Solana client and wallet
solana_client = AsyncClient("https://api.mainnet-beta.solana.com")
wallet = Keypair.from_base58_string(config_settings.wallet_private_key)  # Ensure WALLET_PRIVATE_KEY is in config.py

async def get_sol_price():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd') as resp:
                data = await resp.json()
                return data['solana']['usd']
    except Exception as e:
        logging.error(f"Error fetching SOL price: {e}")
        return 110  # Fallback price

async def get_fee_estimate():
    try:
        min_balance = await solana_client.get_minimum_balance_for_rent_exemption(165)  # Typical size for token account
        return min_balance.value  # Return lamports
    except Exception as e:
        logging.error(f"Error estimating fee: {e}")
        return 1000000  # Fallback fee (1 lamport)

def get_ata(owner: Pubkey, mint: Pubkey):
    return Pubkey.find_program_address(
        seeds=[bytes(owner), bytes(Pubkey.from_string('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA')), bytes(mint)],
        program_id=Pubkey.from_string('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL')
    )[0]

def create_ata_instruction(owner: Pubkey, mint: Pubkey):
    ata = get_ata(owner, mint)
    return create_associated_token_account(owner, owner, mint)

async def create_swap_instruction(token_address: str, amount_in: int, wallet_pubkey: Pubkey, is_buy=True, slippage_tolerance=0.05):
    # Placeholder for actual swap instruction creation
    # This would typically involve interacting with Raydium or another AMM
    # For now, return a dummy instruction
    return transfer(TransferParams(from_pubkey=wallet_pubkey, to_pubkey=FEE_DESTINATION, lamports=amount_in))

async def monitor_token_price(token_address: str, initial_price: float, initial_amount: float, wallet_pubkey: Pubkey, slippage_tolerance: float, contract_id: int):
    token_ata = get_ata(wallet_pubkey, Pubkey.from_string(token_address))
    while True:
        try:
            balance = (await solana_client.get_token_account_balance(token_ata)).value.ui_amount
            sol_price = await get_sol_price()
            current_price = sol_price / balance if balance > 0 else 0
            price_change = (current_price - initial_price) / initial_price

            if price_change >= config_settings.SELL_PROFIT_THRESHOLD:
                await sell_token(token_address, wallet_pubkey, balance, contract_id)
                break
            elif price_change <= -slippage_tolerance:
                await sell_token(token_address, wallet_pubkey, balance, contract_id)
                break

            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logging.error(f"Error monitoring token {token_address}: {e}")
            await asyncio.sleep(60)

async def sell_token(token_address: str, wallet_pubkey: Pubkey, amount: float, contract_id: int):
    try:
        token_ata = get_ata(wallet_pubkey, Pubkey.from_string(token_address))
        wsol_ata = get_ata(wallet_pubkey, WSOL_MINT)
        amount_in_lamports = int(amount * 1e6)  # Assuming 6 decimals for token

        recent_blockhash = await solana_client.get_latest_blockhash()
        instructions = [
            await create_swap_instruction(token_address, amount_in_lamports, wallet_pubkey, is_buy=False)
        ]

        message = Message.new_with_blockhash(instructions, wallet_pubkey, recent_blockhash.value.blockhash)
        transaction = Transaction([wallet], message)
        signature = await solana_client.send_transaction(transaction, opts=TxOpts(skip_confirmation=False))
        logging.info(f"Sell transaction sent with signature: {signature.value}")
        print(f"Sell transaction sent: {signature.value}")

        sol_price = await get_sol_price()
        dollar_value = amount * sol_price
        sell_details = {
            "token_sold": token_address,
            "dollar_value": dollar_value,
            "amount_in_sol": amount,
            "wallet_balance_after": (await solana_client.get_balance(wallet_pubkey)).value / 1e9,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        with db.session.begin():
            contract = Contract.query.get(contract_id)
            if contract:
                contract.status = "sold"
                contract.details = str(sell_details)
            sell_transaction = Transaction(
                contract_id=contract_id,
                token_address=token_address,
                transaction_type="sell",
                amount_in_dollars=dollar_value,
                amount_in_sol=amount,
                slippage_tolerance=0,
                wallet_balance_after=(await solana_client.get_balance(wallet_pubkey)).value / 1e9,
                status="success"
            )
            db.session.add(sell_transaction)
            db.session.commit()

        socketio.emit("sell", sell_details)
    except Exception as e:
        logging.error(f"Error selling token {token_address}: {e}")
        with db.session.begin():
            sell_transaction = Transaction(
                contract_id=contract_id,
                token_address=token_address,
                transaction_type="sell",
                amount_in_dollars=0,
                amount_in_sol=amount,
                slippage_tolerance=0,
                wallet_balance_after=(await solana_client.get_balance(wallet_pubkey)).value / 1e9 if 'solana_client' in globals() else 0,
                status="failed",
                error=str(e)
            )
            db.session.add(sell_transaction)
            db.session.commit()
        socketio.emit("sell_failed", {"token": token_address, "error": str(e), "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

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
            contract = Contract.query.filter_by(address=token_address, group=group).first()
            if contract:
                contract.status = "bought"
                contract.details = str(buy_details)
                print(f"Updated contract {token_address} to status: bought")
            
            buy_transaction = Transaction(
                contract_id=contract.id if contract else None,
                token_address=token_address,
                transaction_type="buy",
                amount_in_dollars=dollar_value,
                amount_in_sol=amount_in_sol,
                slippage_tolerance=slippage_tolerance * 100,
                wallet_balance_after=(await solana_client.get_balance(wallet.pubkey())).value / 1e9,
                status="success"
            )
            db.session.add(buy_transaction)
            db.session.commit()
            print(f"Added buy transaction to database for {token_address}")

        socketio.emit("buy", buy_details)
        asyncio.create_task(monitor_token_price(token_address, initial_price, initial_token_amount, wallet.pubkey(), slippage_tolerance, contract.id if contract else None))

    except Exception as e:
        logging.error(f"Error buying token {token_address}: {e}")
        print(f"Buy failed for {token_address}: {e}")
        with db.session.begin():
            contract = Contract.query.filter_by(address=token_address, group=group).first()
            failed_transaction = Transaction(
                contract_id=contract.id if contract else None,
                token_address=token_address,
                transaction_type="buy",
                amount_in_dollars=dollar_value,
                amount_in_sol=amount_in_sol if 'amount_in_sol' in locals() else 0,
                slippage_tolerance=slippage_tolerance * 100,
                wallet_balance_after=(await solana_client.get_balance(wallet.pubkey())).value / 1e9 if 'solana_client' in globals() else 0,
                status="failed",
                error=str(e)
            )
            db.session.add(failed_transaction)
            db.session.commit()
            print(f"Logged failed buy transaction for {token_address}")
        socketio.emit("buy_failed", {"token": token_address, "error": str(e), "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        raise  # Stop execution to avoid misleading "completed" message
