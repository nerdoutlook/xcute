import re
import logging
from telethon import TelegramClient, events
from datetime import datetime
from config import settings
from websocket_manager import socketio, db, Contract
from buy_program import buy_token
from websocket_manager import app, db  # Import app and db

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.log_dir / "monitor.log"),
        logging.StreamHandler()
    ],
)

# Load Telegram groups
def load_groups():
    try:
        with open(settings.groups_file, "r") as file:
            return [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        logging.error("Error: groups.txt file not found!")
        return []

group_links = load_groups()

# Initialize Telegram client
client = TelegramClient(settings.session_name, settings.api_id, settings.api_hash)

@client.on(events.NewMessage(chats=group_links))
async def new_message_handler(event):
    message = event.message.text
    if not message:
        return

    group_name = event.chat.title or f"Group {event.chat_id}"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    pattern = r"\b[1-9A-Z][1-9A-HJ-NP-Za-km-z]{39}pump\b"
    matches = re.findall(pattern, message)

    if matches:
        contract_address = matches[0].strip()
        if contract_address:
            log_message = f"Detected contract in {group_name}: {contract_address}"
            logging.info(log_message)

            # Create a new contract object
            new_contract = Contract(address=contract_address, group=group_name)

            # Use Flask application context for database operations
            with app.app_context():
                db.session.add(new_contract)
                db.session.commit()

            # Broadcast contract data to WebSocket clients
            socketio.emit("contract", {
                "contract": contract_address,
                "group": group_name,
                "timestamp": current_time
            })

            # Trigger buy logic
            await buy_token(contract_address)
        else:
            logging.warning(f"Empty contract detected in {group_name} (Skipping)")
    else:
        logging.info(f"No contract detected in {group_name}.")


async def start_monitoring():
    await client.start()
    logging.info("Telegram monitoring started.")
    await client.run_until_disconnected()
