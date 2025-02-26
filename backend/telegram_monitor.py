import re
import logging
from telethon import TelegramClient, events
from datetime import datetime
from config import settings
from websocket_manager import socketio, db, app
from buy_program import buy_token
from models import Contract
import asyncio

'''
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.log_dir / "monitor.log"),
        logging.StreamHandler()
    ],
)
'''

def load_groups():
    try:
        with open(settings.groups_file, "r") as file:
            groups = [line.strip() for line in file.readlines() if line.strip()]
        if not groups:
            logging.warning("No groups found in groups.txt")
            print("No groups found in groups.txt")
        print(f"Loaded groups: {groups}")
        return groups
    except FileNotFoundError:
        logging.error(f"Error: {settings.groups_file} not found!")
        print(f"Error: {settings.groups_file} not found!")
        return []
    except Exception as e:
        logging.error(f"Error loading groups: {e}")
        print(f"Error loading groups: {e}")
        return []

group_links = load_groups()

async def start_monitoring(session_name="telegram_monitor_session"):
    client = TelegramClient(session_name, settings.api_id, settings.api_hash)
    if not group_links:
        logging.error("No groups to monitor. Exiting.")
        print("No groups to monitor. Exiting.")
        return
    try:
        await client.start()
        logging.info("Telegram client connected successfully.")
        print("Telegram client started and connected.")
        async for dialog in client.iter_dialogs():
            chat_id = dialog.entity.id
            if str(chat_id) in [str(chat.id) if hasattr(chat, 'id') else chat.split('/')[-1] for chat in group_links]:
                print(f"Monitoring chat: {dialog.title} (ID: {chat_id})")

        @client.on(events.NewMessage(chats=group_links))
        async def new_message_handler(event):
            message = event.message.text
            print(f"New message received from {event.chat_id}: '{message}'")
            if not message:
                print(f"Empty message from {event.chat_id}")
                return

            group_name = event.chat.title or f"Group {event.chat_id}"
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            matches = re.findall(PUMP_FUN_ADDRESS_PATTERN, message)
            print(f"Regex matches for '{message}': {matches}")
            if not matches:
                logging.info(f"No Pump.fun contract detected in {group_name}.")
                print(f"No contracts found in {group_name} message: '{message}'")
                return

            for match in matches:
                contract_address = match[:-4]  # Strip "pump"
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
                    # Run buy_token within app context
                    with app.app_context():
                        await buy_token(contract_address, group_name)
                    print(f"Buy transaction completed for {contract_address}")

                except Exception as e:
                    with app.app_context():
                        db.session.rollback()
                    logging.error(f"Error processing contract {contract_address} in {group_name}: {e}", exc_info=True)
                    print(f"Failed to buy {contract_address}: {e}")

                await asyncio.sleep(1)

        async def keepalive():
            while True:
                print("Telegram client still alive...")
                await asyncio.sleep(10)

        asyncio.create_task(keepalive())
        await client.run_until_disconnected()
    except Exception as e:
        logging.error(f"Error starting Telegram client: {e}", exc_info=True)
        print(f"Telegram client failed to start: {e}")

PUMP_FUN_ADDRESS_PATTERN = r"\b[1-9A-HJ-NP-Za-km-z]{44}\b"  # Match full 44-char Pump.fun address

if __name__ == "__main__":
    asyncio.run(start_monitoring())
