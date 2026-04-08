from sqlalchemy import create_engine, text
from database import SQLALCHEMY_DATABASE_URL

engine = create_engine(SQLALCHEMY_DATABASE_URL)
with engine.connect() as conn:
    print("Altering projects table...")
    try:
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS running_summary TEXT;"))
        conn.commit()
        print("Success.")
    except Exception as e:
        print("Error:", e)
