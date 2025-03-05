
import logging
import multiprocessing
import os
import sys
import signal
import asyncio
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from telegram_monitor import start_monitoring
from config import settings
from models import Contract, Transaction
from buy_program import solana_client, wallet

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = settings.secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# CORS for HTTP API endpoints
CORS(app, resources={r"/api/*": {"origins": "https://xcute-six.vercel.app"}})

# Initialize SocketIO and DB
socketio = SocketIO(app, cors_allowed_origins=["https://xcute.onrender.com", "https://xcute-six.vercel.app"], engineio_logger=True)
db = SQLAlchemy(app)

def init_db():
    with app.app_context():
        db.create_all()
        logging.info("Database tables created.")

# API Endpoints
@app.route("/api/contracts")
def get_contracts():
    with app.app_context():
        contracts = Contract.query.order_by(Contract.timestamp.desc()).all()
        return jsonify([{
            "id": contract.id,
            "address": contract.address,
            "group": contract.group,
            "status": contract.status,
            "timestamp": contract.timestamp.isoformat(),
            "details": contract.details
        } for contract in contracts])

@app.route("/api/transactions")
def get_transactions():
    with app.app_context():
        transactions = Transaction.query.order_by(Transaction.timestamp.desc()).all()
        return jsonify([{
            "id": transaction.id,
            "contract_id": transaction.contract_id,
            "token_address": transaction.token_address,
            "transaction_type": transaction.transaction_type,
            "amount_in_dollars": transaction.amount_in_dollars,
            "amount_in_sol": transaction.amount_in_sol,
            "slippage_tolerance": transaction.slippage_tolerance,
            "wallet_balance_after": transaction.wallet_balance_after,
            "timestamp": transaction.timestamp.isoformat(),
            "status": transaction.status,
            "error": transaction.error
        } for transaction in transactions])

@app.route("/api/wallet_balance")
async def get_wallet_balance():
    try:
        balance = (await solana_client.get_balance(wallet.pubkey())).value / 1e9
        return jsonify({"balance": balance})
    except Exception as e:
        logging.error(f"Wallet balance error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/test")
def test():
    return jsonify({"status": "Backend is alive"})

@socketio.on("connect")
def handle_connect():
    logging.info("Client connected")
    print("WebSocket client connected")
    socketio.emit("log", {"message": "WebSocket connection established."})

@socketio.on("disconnect")
def handle_disconnect():
    logging.info("Client disconnected")
    print("WebSocket client disconnected")

def run_telegram_monitoring():
    """Run Telegram monitoring in a separate process."""
    from telegram_monitor import start_monitoring
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 1)
    sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 1)
    print(f"Telegram subprocess started, PID: {os.getpid()}, Session: telegram_monitor_session")
    asyncio.run(start_monitoring(session_name="telegram_monitor_session"))

def cleanup_subprocess(process):
    if process and process.is_alive():
        logging.info("Terminating Telegram subprocess with PID: %d", process.pid)
        print(f"Terminating Telegram subprocess with PID: {process.pid}")
        process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            os.kill(process.pid, signal.SIGKILL)
            process.join()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(settings.log_dir / "server.log"),
            logging.StreamHandler()
        ],
    )
    logging.info("Initializing database...")
    print("Initializing database...")
    init_db()

    telegram_process = multiprocessing.Process(target=run_telegram_monitoring, name="TelegramMonitor")
    telegram_process.start()
    logging.info("Telegram monitoring process started with PID: %d", telegram_process.pid)
    print(f"Telegram monitoring process started with PID: {telegram_process.pid}")

    logging.info("Starting Flask-SocketIO server...")
    print("Starting Flask server...")
    try:
        def signal_handler(sig, frame):
            cleanup_subprocess(telegram_process)
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        socketio.run(app, host="0.0.0.0", port=8000, debug=False)
    except KeyboardInterrupt:
        logging.info("Server stopped by user.")
        print("Server stopped.")
        cleanup_subprocess(telegram_process)
    except Exception as e:
        logging.error(f"Server error: {e}", exc_info=True)
        print(f"Server error: {e}")
        cleanup_subprocess(telegram_process)
    finally:
        cleanup_subprocess(telegram_process)
