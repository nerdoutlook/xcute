import logging
from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from config import settings
from flask_session import Session

app = Flask(__name__)
app.config["SECRET_KEY"] = settings.secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQLAlchemy(app)
# Allow CORS for SocketIO, including the Flask server origin
socketio = SocketIO(app, cors_allowed_origins=["http://127.0.0.1:8000", "http://localhost:8000"], engineio_logger=True)

from models import Contract, Transaction

def init_db():
    with app.app_context():
        db.create_all()
        logging.info("Database tables created.")
