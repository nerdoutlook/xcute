from flask import Flask, render_template
from websocket_manager import socketio, app
import logging
import asyncio
from telegram_monitor import start_monitoring
from config import settings

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.log_dir / "server.log"),
        logging.StreamHandler()
    ],
)

# Serve the frontend
@app.route("/")
def serve_home():
    return render_template("index.html")

# WebSocket event for client connection
@socketio.on("connect")
def handle_connect():
    logging.info("Client connected")
    socketio.emit("log", {"message": "WebSocket connection established."})

# WebSocket event for client disconnection
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
