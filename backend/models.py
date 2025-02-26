from datetime import datetime
from main import db  # Import db from main.py

class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(44), nullable=False, index=True)
    group = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(10), nullable=False)  # "found", "bought", "sold"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    details = db.Column(db.Text, nullable=True)  # Additional details as JSON string

    # Optional: Add relationship for transactions
    transactions = db.relationship('Transaction', backref='contract', lazy=True)

    def __repr__(self):
        return f"<Contract {self.address} from {self.group} - {self.status} at {self.timestamp}>"

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'), nullable=True)
    token_address = db.Column(db.String(44), nullable=False, index=True)
    transaction_type = db.Column(db.String(4), nullable=False)  # "buy", "sell"
    amount_in_dollars = db.Column(db.Float, nullable=False)
    amount_in_sol = db.Column(db.Float, nullable=False)
    slippage_tolerance = db.Column(db.Float, nullable=False)
    wallet_balance_after = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    status = db.Column(db.String(10), nullable=False, default="pending")  # "pending", "success", "failed"
    error = db.Column(db.Text, nullable=True)  # Error message for failed attempts

    def __repr__(self):
        return f"<Transaction {self.transaction_type} {self.token_address} for {self.amount_in_dollars} USD at {self.timestamp} - {self.status}>"
