from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

socketio = SocketIO()
db = SQLAlchemy()

def init_db():
    db.create_all()
    logging.info("Database tables created.")
