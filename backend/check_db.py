from database import engine, SessionLocal
from models import ChatMessage
from sqlalchemy import inspect

def check_db():
    inspector = inspect(engine)
    if 'chat_messages' in inspector.get_table_names():
        print("Table 'chat_messages' exists.")
        db = SessionLocal()
        count = db.query(ChatMessage).count()
        print(f"Chat messages count: {count}")
    else:
        print("Table 'chat_messages' DOES NOT EXIST.")

if __name__ == "__main__":
    check_db()
