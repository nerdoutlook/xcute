import re
import logging
from telethon import TelegramClient, events
from datetime import datetime
from config import settings
from websocket_manager import socketio, db, app
from buy_program import buy_token
from models import Contract
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.log_dir / "monitor.log"),
        logging.StreamHandler()
    ],
)

def load_groups():
    try:
        with open(settings.groups_file, "r") as file:
            groups = [line.strip() for line in file.readlines() if line.strip()]
        if not groups:
            logging.warning("No groups found in groups.txt")
        return groups
    except FileNotFoundError:
        logging.error(f"Error: {settings.groups_file} not found!")
        return []
    except Exception as e:
        logging.error(f"Error loading groups: {e}")
        return []

group_links = load_groups()
client = TelegramClient(settings.session_name, settings.api_id, settings.api_hash)

# Updated regex: Match 43-44 char Solana addresses followed by "pump"
PUMP_FUN_ADDRESS_PATTERN = r"\b[1-9A-HJ-NP-Za-km-z]{42,43}pump\b"

@client.on(events.NewMessage(chats=group_links))
async def new_message_handler(event):
    message = event.message.text
    if not message:
        return

    group_name = event.chat.title or f"Group {event.chat_id}"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    matches = re.findall(PUMP_FUN_ADDRESS_PATTERN, message)
    if not matches:
        logging.info(f"No Pump.fun contract detected in {group_name}.")
        print(f"No contracts found in {group_name} message: {message}")
        return

    for match in matches:
        # Extract the address (remove "pump" suffix)
        contract_address = match[:-4]  # Strip "pump" from the end
        log_message = f"Detected Pump.fun contract in {group_name}: {contract_address}"
        logging.info(log_message)
        print(f"Found contract: {contract_address} in {group_name} at {current_time}")

        try:
            with app.app_context():
                new_contract = Contract(address=contract_address, group=group_name, status="found", timestamp=datetime.now())
                db.session.add(new_contract)
                db.session.commit()
                contract_id = new_contract.id
                print(f"Added contract {contract_address} to database with ID {contract_id}, status: found")

            socketio.emit("contract", {
                "contract": contract_address,
                "group": group_name,
                "timestamp": current_time
            })

            print(f"Attempting to buy token: {contract_address}")
            await buy_token(contract_address, group_name)
            print(f"Buy transaction completed for {contract_address}")

        except Exception as e:
            with app.app_context():
                db.session.rollback()
            logging.error(f"Error processing contract {contract_address} in {group_name}: {e}", exc_info=True)
            print(f"Failed to buy {contract_address}: {e}")

        await asyncio.sleep(1)

async def start_monitoring():
    if not group_links:
        logging.error("No groups to monitor. Exiting.")
        return
    try:
        await client.start()
        logging.info("Telegram client connected successfully.")
        print("Telegram client started and connected.")
        await client.run_until_disconnected()
    except Exception as e:
        logging.error(f"Error starting Telegram client: {e}", exc_info=True)
        print(f"Telegram client failed to start: {e}")

if __name__ == "__main__":
    asyncio.run(start_monitoring())
