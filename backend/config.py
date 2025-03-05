import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env")  # Explicitly load .env file
print(f"Current Working Directory: {os.getcwd()}")

class Settings:
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
#    bot_token = os.getenv("BOT_TOKEN")  # Added for Telegram bot
    secret_key = os.getenv("secret_key")
    database_uri = os.getenv("DATABASE_URI", f"sqlite:///{Path(__file__).parent / 'app.db'}")
    cors_allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    session_name = "telegram_monitor"
    groups_file = Path("groups.txt")
    log_dir = Path("logs")
    wallet_private_key = os.getenv("WALLET_PRIVATE_KEY")
    BUY_DOLLAR_VALUE = 1.0
    SLIPPAGE_TOLERANCE = 0.05  # 5%
    PROFIT_THRESHOLD = 2.0  # 2x
    SELL_PROFIT_FACTOR = 1.5  # Sell 1.5x on profit
    LOSS_THRESHOLD = 0.45  # 55% drop (45% of initial price)

settings = Settings()
print(f"Database URI from settings: {settings.database_uri}")
