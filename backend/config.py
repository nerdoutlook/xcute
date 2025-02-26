import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env")
print(f"Current Working Directory: {os.getcwd()}")

class Settings:
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    secret_key = os.getenv("secret_key")
    database_uri = os.getenv("DATABASE_URI", f"sqlite:///{Path(__file__).parent / 'app.db'}")
    cors_allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    session_name = "telegram_monitor"
    groups_file = Path("groups.txt")
    log_dir = Path("logs")
    wallet_private_key = os.getenv("WALLET_PRIVATE_KEY")
    BUY_DOLLAR_VALUE = 1.0
    SLIPPAGE_TOLERANCE = 0.05
    PROFIT_THRESHOLD = 2.0
    SELL_PROFIT_FACTOR = 1.5
    LOSS_THRESHOLD = 0.45

settings = Settings()
print(f"Database URI from settings: {settings.database_uri}")
