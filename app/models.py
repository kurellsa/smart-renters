from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from .database import Base
from datetime import datetime

class RentalStatement(Base):
    __tablename__ = "rental_statements"

    id = Column(Integer, primary_key=True, index=True)
    property_name = Column(String, index=True)
    statement_date = Column(String)  # Storing as string to match LLM output easily
    rent_amount = Column(Float)
    fees = Column(Float)
    net_income = Column(Float)
    raw_json = Column(JSON)          # Stores the full LLM dictionary
    created_at = Column(DateTime, default=datetime.utcnow)

class ReconciliationLog(Base):
    __tablename__ = "reconciliation_logs"

    id = Column(Integer, primary_key=True, index=True)
    property_name = Column(String)
    pdf_rent = Column(Float)
    bank_rent = Column(Float)
    difference = Column(Float)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)