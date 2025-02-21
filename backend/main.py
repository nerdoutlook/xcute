from flask import Flask, render_template, jsonify
from websocket_manager import socketio, app, db
import logging
import asyncio
from telegram_monitor import start_monitoring
from config import settings
from flask import Flask, render_template, send_from_directory

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.log_dir / "server.log"),
        logging.StreamHandler()
    ],
)

app = Flask(__name__, static_folder="../frontend/build/static", template_folder="../frontend/build")

# Serve static files from the React build directory
@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# Serve the frontend
@app.route("/")
def serve_home():
    return render_template("index.html")

# API endpoints
@app.route("/api/contracts")
def get_contracts():
    contracts = Contract.query.order_by(Contract.timestamp.desc()).all()
    return jsonify([{
        "address": contract.address,
        "group": contract.group,
        "timestamp": contract.timestamp
    } for contract in contracts])

@app.route("/api/transactions")
def get_transactions():
    transactions = Transaction.query.order_by(Transaction.timestamp.desc()).all()
    return jsonify([{
        "token_bought": transaction.token_bought,
        "amount_bought": transaction.amount_bought,
        "slippage_paid": transaction.slippage_paid,
        "wallet_balance_after": transaction.wallet_balance_after,
        "timestamp": transaction.timestamp
    } for transaction in transactions])

# WebSocket events
@socketio.on("connect")
def handle_connect():
    logging.info("Client connected")
    socketio.emit("log", {"message": "WebSocket connection established."})

@socketio.on("disconnect")
def handle_disconnect():
    logging.info("Client disconnected")

# Start the Telegram monitor when the server starts
def start_background_tasks():
    asyncio.run(start_monitoring())

# Start the background task when the app starts
start_background_tasks()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8000, debug=True)
