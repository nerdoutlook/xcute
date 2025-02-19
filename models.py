from pydantic import BaseModel
from datetime import datetime

class ContractUpdate(BaseModel):
    contract: str
    group: str
    timestamp: str

class BuyTransaction(BaseModel):
    token_bought: str
    amount_bought: float
    slippage_paid: float
    wallet_balance_after: float
    timestamp: str
