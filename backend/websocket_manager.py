from main import socketio, db

def init_db():
    db.create_all()
    logging.info("Database tables created.")
