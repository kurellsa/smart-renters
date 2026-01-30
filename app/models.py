from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from .database import Base
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List

class PropertyDetail(BaseModel):
    address: str
    rent_amount: float  # Changed from 'rent' to match LLM
    rent_paid: float
    management_fees: float
    net_income: float

class ExtractedDoc(BaseModel):
    statement_date: str
    merchant_group: str
    properties: List[PropertyDetail] 

class ReconciliationLog(Base):
    __tablename__ = "reconciliation_logs"

    id = Column(Integer, primary_key=True, index=True)
    property_name = Column(String)
    pdf_rent = Column(Float)
    bank_rent = Column(Float)
    difference = Column(Float)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)