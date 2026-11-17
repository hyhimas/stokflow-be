import os
import ssl
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Ensure connection string uses pg8000 dialect for seamless pure-Python PostgreSQL connection
clean_url = DATABASE_URL.split("?")[0]
if clean_url.startswith("postgresql+psycopg://"):
    clean_url = clean_url.replace("postgresql+psycopg://", "postgresql+pg8000://")
elif clean_url.startswith("postgresql://"):
    clean_url = clean_url.replace("postgresql://", "postgresql+pg8000://")

# Setup SSL context required for Neon Cloud Database
ssl_context = ssl.create_default_context()

engine = create_engine(
    clean_url,
    connect_args={"ssl_context": ssl_context},
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
