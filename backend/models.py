from datetime import datetime
from websocket_manager import db

class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(120), nullable=False)
    group = db.Column(db.String(120), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token_bought = db.Column(db.String(120), nullable=False)
    amount_bought = db.Column(db.Float, nullable=False)
    slippage_paid = db.Column(db.Float, nullable=False)
    wallet_balance_after = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
