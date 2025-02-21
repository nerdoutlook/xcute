import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env")  # Explicitly load .env file

print(f"Current Working Directory: {os.getcwd()}")

class Settings:
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    session_name = "telegram_monitor"
    groups_file = Path("groups.txt")
    log_dir = Path("logs")
#    wallet_private_key = ("3VPiUrSqou823B8Y1NdwwsURweC7jBYNqv7acXs28NtAQXzwLCaasEWvQnktbs3Jiu69LxZWZkQa9c3qkC9dLE69")
    wallet_private_key = os.getenv("WALLET_PRIVATE_KEY")

settings = Settings()
