import re
import logging
from telethon import TelegramClient, events
from datetime import datetime
from config import settings
from buy_program import buy_token
import asyncio
import os
import traceback

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
    from main import socketio, db, app, Contract

    client = TelegramClient(session_name, settings.api_id, settings.api_hash)
    if not group_links:
        logging.error("No groups to monitor. Exiting.")
        print("No groups to monitor. Exiting.")
        return

    session_file = f"{session_name}.session"
    if not os.path.exists(session_file):
        logging.error(f"Session file {session_file} not found. Run generate_session.py locally to create it.")
        print(f"Error: Session file {session_file} not found. Run generate_session.py locally to create it.")
        return

    try:
        await client.connect()
        if not await client.is_user_authorized():
            logging.error("Client not authorized. Ensure the session file is valid and matches TELEGRAM_PHONE.")
            print("Error: Client not authorized. Regenerate the session file with generate_session.py.")
            await client.disconnect()
            return

        logging.info("Telegram client connected successfully.")
        print("Telegram client started and connected.")
        async for dialog in client.iter_dialogs():
            chat_id = dialog.entity.id
            if str(chat_id) in [str(chat.id) if hasattr(chat, 'id') else chat.split('/')[-1] for chat in group_links]:
                print(f"Monitoring chat: {dialog.title} (ID: {chat_id})")

        @client.on(events.NewMessage(chats=group_links))
        async def new_message_handler(event):
            message_text = event.message.text or event.message.message or ""
            print(f"New message received from {event.chat_id}: '{message_text}'")
            logging.info(f"Raw message content: {repr(event.message)}")
            logging.info(f"Message attributes - text: {event.message.text}, message: {event.message.message}, entities: {event.message.entities}, media: {event.message.media}")

            if not message_text:
                if event.message.media:
                    if hasattr(event.message.media, 'webpage') and event.message.media.webpage:
                        message_text = event.message.media.webpage.url or ""
                        print(f"Extracted webpage URL: {message_text}")
                    elif hasattr(event.message.media, 'document') and event.message.media.document:
                        message_text = event.message.message or ""
                        print(f"Media caption: {message_text}")
                    elif str(event.message.media) == 'MessageMediaUnsupported()':
                        # Fallback: Fetch raw message content via API
                        full_message = await client.get_messages(event.chat_id, ids=event.message.id)
                        message_text = full_message[0].message or ""
                        print(f"Fallback fetch for unsupported media: {message_text}")
                if not message_text:
                    print(f"Empty message from {event.chat_id}")
                    return

            group_name = event.chat.title or f"Group {event.chat_id}"
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            matches = re.findall(PUMP_FUN_ADDRESS_PATTERN, message_text)
            print(f"Regex matches for '{message_text}': {matches}")
            if not matches:
                logging.info(f"No Pump.fun contract detected in {group_name}.")
                print(f"No contracts found in {group_name} message: '{message_text}'")
                return

            for match in matches:
                contract_address = match
                log_message = f"Detected Pump.fun contract in {group_name}: {contract_address}"
                logging.info(log_message)
                print(f"Found contract: {contract_address} in {group_name} at {current_time}")

                try:
                    with app.app_context():
                        new_contract = Contract(
                            address=contract_address,
                            group=group_name,
                            status="found",
                            timestamp=datetime.now()
                        )
                        db.session.add(new_contract)
                        db.session.commit()
                        contract_id = new_contract.id
                        print(f"Added contract {contract_address} to database with ID {contract_id}, status: found")

                        socketio.emit("contract", {
                            "contract": contract_address,
                            "group": group_name,
                            "timestamp": current_time
                        })
                        print(f"Emitted contract event: {contract_address}")
                        logging.info(f"Emitted contract event: {contract_address}")

                        print(f"Attempting to buy token: {contract_address}")
                        await buy_token(contract_address, group_name)
                        print(f"Buy transaction completed for {contract_address}")

                except Exception as e:
                    with app.app_context():
                        db.session.rollback()
                    logging.error(f"Error processing contract {contract_address} in {group_name}: {e}", exc_info=True)
                    print(f"Failed to buy {contract_address}: {e}")

                await asyncio.sleep(1)

        async def keep_alive(client):
            while True:
                try:
                    dialogs = await client.get_dialogs(limit=1)
                    logging.info("Keep-alive: Fetched dialogs to maintain Render activity.")
                    print("Keep-alive: Fetched dialogs.")
                except Exception as e:
                    logging.error(f"Keep-alive error: {e}", exc_info=True)
                    print(f"Keep-alive error: {e}")
                await asyncio.sleep(300)

        async def keepalive():
            while True:
                print("Telegram client still alive...")
                await asyncio.sleep(10)

        async def fetch_recent_messages(client):
            while True:
                print("Fetching recent messages...")
                logging.info("Starting recent message fetch cycle")
                try:
                    for group in group_links:
                        async for message in client.iter_messages(group, limit=5):
                            text = message.text or message.message or ""
                            if message.media:
                                if hasattr(message.media, 'webpage') and message.media.webpage:
                                    text = message.media.webpage.url or ""
                                    print(f"Recent message webpage URL: {text}")
                                elif hasattr(message.media, 'document'):
                                    text = message.message or ""
                                    print(f"Recent message media caption: {text}")
                                elif str(message.media) == 'MessageMediaUnsupported()':
                                    full_message = await client.get_messages(group, ids=message.id)
                                    text = full_message[0].message or ""
                                    print(f"Recent message fallback fetch: {text}")
                            print(f"Recent message check from {group}: '{text}'")
                            matches = re.findall(PUMP_FUN_ADDRESS_PATTERN, text)
                            if matches:
                                logging.info(f"Found recent contract: {matches}")
                except Exception as e:
                    logging.error(f"Recent message fetch error: {e}", exc_info=True)
                    print(f"Recent message fetch error: {e}")
                await asyncio.sleep(60)

        asyncio.create_task(keep_alive(client))
        asyncio.create_task(keepalive())
        asyncio.create_task(fetch_recent_messages(client))
        logging.info("Starting Telegram client event loop.")
        await client.run_until_disconnected()
    except Exception as e:
        logging.error(f"Critical error in Telegram client: {e}\n{traceback.format_exc()}")
        print(f"Critical error in Telegram client: {e}")
    finally:
        logging.info("Disconnecting Telegram client.")
        await client.disconnect()

PUMP_FUN_ADDRESS_PATTERN = r"\b[1-9A-HJ-NP-Za-km-z]{44}\b"

if __name__ == "__main__":
    asyncio.run(start_monitoring())
