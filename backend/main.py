import logging
import asyncio
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from websocket_manager import socketio, app, db, init_db
from telegram_monitor import start_monitoring
from config import settings
from models import Contract, Transaction

CORS(app, supports_credentials=True)

app.static_folder = os.path.abspath("../frontend/build")
app.template_folder = os.path.abspath("../frontend/build")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.log_dir / "server.log"),
        logging.StreamHandler()
    ],
)

logging.info(f"Static folder: {app.static_folder}")
logging.info(f"Template folder: {app.template_folder}")

@app.route("/_next/<path:path>")
def serve_next_static(path):
    full_path = os.path.join(app.static_folder, "_next", path)
    logging.info(f"Serving static file: {full_path}")
    return send_from_directory(os.path.join(app.static_folder, "_next"), path)

@app.route("/favicon.ico")
def serve_favicon():
    full_path = os.path.join(app.static_folder, "favicon.ico")
    logging.info(f"Serving favicon: {full_path}")
    return send_from_directory(app.static_folder, "favicon.ico")

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_home(path):
    file_name = f"{path}.html" if path else "index.html"
    full_path = os.path.join(app.template_folder, file_name)
    logging.info(f"Serving page: {full_path}")
    try:
        return send_from_directory(app.template_folder, file_name)
    except FileNotFoundError:
        logging.info(f"Fallback to index.html: {os.path.join(app.template_folder, 'index.html')}")
        return send_from_directory(app.template_folder, "index.html")

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
            "timestamp": transaction.timestamp.isoformat()
        } for transaction in transactions])

@socketio.on("connect")
def handle_connect():
    logging.info("Client connected")
    print("WebSocket client connected")
    socketio.emit("log", {"message": "WebSocket connection established."})

@socketio.on("disconnect")
def handle_disconnect():
    logging.info("Client disconnected")
    print("WebSocket client disconnected")

async def start_background_tasks():
    logging.info("Starting background tasks...")
    print("Initializing database and starting Telegram monitoring...")
    init_db()
    asyncio.create_task(start_monitoring())
    logging.info("Telegram monitoring task scheduled.")
    print("Telegram monitoring started.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_background_tasks())
    socketio.run(app, host="0.0.0.0", port=8000, debug=True)
