from sqlalchemy import Column, Integer, Date, String, Float, DateTime, JSON
from app.database import Base
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List

class PropertyDetail(BaseModel):
    address: str = Field(default="Unknown Address")
    rent_amount: float = Field(default=0.0)
    rent_paid: float = Field(default=0.0)
    management_fees: float = Field(default=0.0)
    net_income: float = Field(default=0.0)

class ExtractedDoc(BaseModel):
    statement_date: str
    merchant_group: str
    properties: List[PropertyDetail] = Field(default_factory=list)

class RentalStatement(Base):
    __tablename__ = "rental_statements"

    id = Column(Integer, primary_key=True, index=True)
    statement_date = Column(Date, nullable=False)
    merchant_group = Column(String)  # GOGO or SURE
    address = Column(String)
    rent_amount = Column(Float)
    rent_paid = Column(Float)
    management_fees = Column(Float)
    net_income = Column(Float)
    source_file = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class ReconciliationSummary(Base):
    __tablename__ = "reconciliation_summary"

    id = Column(Integer, primary_key=True, index=True)
    statement_date = Column(Date, nullable=False)
    merchant_group = Column(String)  # GOGO or SURE
    bank_transaction = Column(Float)
    statement_total = Column(Float)
    difference = Column(Float)
    status = Column(String) # MATHCED or DISCREPANCY
    property_count=Column(Float)
    source_file = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)