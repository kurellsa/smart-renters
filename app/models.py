from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from .database import Base
from datetime import datetime
class RentalStatement(Base):
    __tablename__ = "rental_statements"

    id = Column(Integer, primary_key=True, index=True)
    statement_date = Column(String)    # Date reported on the PDF
    address = Column(String, index=True)
    rent_amount = Column(Float)          # Actual income (to match bank)
    rent_paid = Column(Float)          # Actual income (to match bank)
    management_fees = Column(Float)    # Expense
    net_income = Column(Float)         # Calculated field (Paid - Fees)
    merchant_group = Column(String)    #"GOGO PROPERTY" or "SURE REALTY"
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