from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from .database import Base
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List

class PropertyDetail(BaseModel):
    address: str
    rent_amount: float
    rent_paid: float
    management_fees: float
    net_income: float

class ExtractedDoc(BaseModel):
    statement_date: str
    merchant_group: str
    properties: List[PropertyDetail] 

class RentalStatement(Base):
    __tablename__ = "rental_statements"

    id = Column(Integer, primary_key=True, index=True)
    statement_date = Column(String)  # From LLM
    merchant_group = Column(String)  # GOGO or SURE
    address = Column(String)
    rent_amount = Column(Float)
    rent_paid = Column(Float)
    management_fees = Column(Float)
    net_income = Column(Float)
    source_file = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)