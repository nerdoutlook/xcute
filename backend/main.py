from flask import Flask, jsonify
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import settings
from solana.rpc.async_api import AsyncClient
import asyncio
import logging
import os
from solders.keypair import Keypair
import telegram_monitor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler(os.path.join(settings.log_dir, 'app.log'))
file_handler.setLevel(logging.INFO)
logging.getLogger('').addHandler(file_handler)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = settings.database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins=["https://xcute.onrender.com", "https://xcute-six.vercel.app"])
CORS(app)

class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(44), nullable=False)
    group = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token_address = db.Column(db.String(44), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    amount_in_dollars = db.Column(db.Float, nullable=False)
    amount_in_sol = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    error = db.Column(db.String(500))
    signature = db.Column(db.String(88))
    timestamp = db.Column(db.DateTime, nullable=False)

solana_client = AsyncClient("https://api.mainnet-beta.solana.com")
wallet = Keypair.from_base58_string(os.getenv("WALLET_PRIVATE_KEY"))

@app.route("/api/contracts")
def get_contracts():
    contracts = Contract.query.all()
    return jsonify([{"contract": c.address, "group": c.group, "timestamp": c.timestamp.isoformat()} for c in contracts])

@app.route("/api/transactions")
def get_transactions():
    transactions = Transaction.query.all()
    return jsonify([{
        "token_address": t.token_address,
        "transaction_type": t.transaction_type,
        "amount_in_dollars": t.amount_in_dollars,
        "amount_in_sol": t.amount_in_sol,
        "status": t.status,
        "error": t.error,
        "signature": t.signature,
        "timestamp": t.timestamp.isoformat()
    } for t in transactions])

@app.route("/api/wallet_balance")
async def get_wallet_balance():
    try:
        async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
            balance = (await client.get_balance(wallet.pubkey())).value / 1e9
        return jsonify({"balance": balance})
    except Exception as e:
        logging.error(f"Wallet balance error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@socketio.on("connect")
def handle_connect():
    logging.info("Client connected")
    socketio.emit("log", {"message": "WebSocket connection established."})

@socketio.on("disconnect")
def handle_disconnect():
    logging.info("Client disconnected")

def run_telegram_monitor():
    pid = os.fork()
    if pid == 0:
        asyncio.run(telegram_monitor.start_monitoring())
        os._exit(0)
    else:
        logging.info(f"Telegram monitoring process started with PID: {pid}")
        print(f"Telegram monitoring process started with PID: {pid}")
        return pid

if __name__ == "__main__":
    logging.info("Initializing database...")
    print("Initializing database...")
    with app.app_context():
        db.create_all()
    logging.info("Database tables created.")

    telegram_pid = run_telegram_monitor()
    logging.info("Starting Flask-SocketIO server...")
    print("Starting Flask server...")
    try:
        socketio.run(app, host="0.0.0.0", port=8000, use_reloader=False)
    finally:
        logging.info(f"Terminating Telegram subprocess with PID: {telegram_pid}")
        os.kill(telegram_pid, 15)
