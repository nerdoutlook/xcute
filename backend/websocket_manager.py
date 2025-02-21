from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"  # SQLite database

# Initialize extensions
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Import models (defined in models.py)
from models import Contract, Transaction

# Create database tables
with app.app_context():
    db.create_all()
