import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Get URL from HF Secrets
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Fix for SQLAlchemy if the URL starts with 'postgres://' (common in cloud providers)
if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_pre_ping=True,  # Critical for Neon "Scale to Zero"
    pool_recycle=300     # Refreshes connections every 5 mins
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get DB session in routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()