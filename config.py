from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Telegram credentials
    api_id: int
    api_hash: str
    session_name: str

    # Solana RPC URL
    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"

    # Wallet private key
    wallet_private_key: str  # Add this field

    # File paths
    groups_file: Path = Path("groups.txt")
    log_dir: Path = Path("logs")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
