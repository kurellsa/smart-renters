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
    property_management: str = Field(default="Unknown")

class ExtractedDoc(BaseModel):
    statement_date: str
    property_management: str
    properties: List[PropertyDetail] = Field(default_factory=list)

class RentalStatement(Base):
    __tablename__ = "rental_statements"

    id = Column(Integer, primary_key=True, index=True)
    statement_date = Column(Date, nullable=False)
    property_management = Column(String)  # GOGO or SURE
    address = Column(String)
    rent_amount = Column(Float)
    rent_paid = Column(Float)
    management_fees = Column(Float)
    net_income = Column(Float)
    source_file = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class PropertyParameter(Base):
    __tablename__ = "property_parameters"
    
    id = Column(Integer, primary_key=True, index=True)
    property_management = Column(String, nullable=True) # Values: 'GOGO', 'SURE', 'Self-Managed'
    address = Column(String, nullable=False)  # Maps to 'Property'
    expected_rent = Column(Float)             # Maps to 'Rental_Income'
    management_fee = Column(Float)             # Maps to 'Management_Fee'
    mortgage_payment = Column(Float)          # Maps to 'Mortgage_Payment'
    hoa_fee = Column(Float)                   # Maps to 'HOA'
    hoa_frequency = Column(String)            # Maps to 'HOA_Frequency' (M/Q)
    hoa_account_no = Column(String)           # Maps to 'HOA_Account_No'
    hoa_phone_no = Column(String)             # Maps to 'HOA_Phone_No'
    notes = Column(String)                    # Maps to 'Notes'

    # Versioning
    effective_from = Column(Date, default=datetime.utcnow().date)
    effective_to = Column(Date, nullable=True)

class PropertyReconLog(Base):
    __tablename__ = "property_recon_log"
    
    id = Column(Integer, primary_key=True, index=True)
    month_year = Column(Date, nullable=False)  # e.g., 2026-02-01
    address = Column(String, nullable=False)
    property_management = Column(String, nullable=False)
    
    # Rent Fields
    target_rent = Column(Float, default=0.0)
    actual_rent = Column(Float, default=0.0)
    rent_variance = Column(Float, default=0.0)
    
    # HOA Fields
    target_hoa = Column(Float, default=0.0)
    actual_hoa = Column(Float, default=0.0)
    hoa_variance = Column(Float, default=0.0)

    # Mortgage Fields
    target_mortgage = Column(Float, default=0.0)
    actual_mortgage = Column(Float, default=0.0)
    mortgage_variance = Column(Float, default=0.0)
        
    bank_deposit_total = Column(Float, default=0.0)
    # Metadata
    status = Column(String)  # "MATCHED", "DISCREPANCY", "MISSING"
    created_at = Column(DateTime, default=datetime.utcnow)

class MiscExpenseLog(Base):
    __tablename__ = "misc_expense_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    month_year = Column(Date, nullable=False)
    date_cleared = Column(Date) # From Baselane CSV
    description = Column(String) # Raw bank text
    amount = Column(Float)
    category_suggestion = Column(String) # e.g., "Repairs", "Bank Fee"
    property_id = Column(Integer, nullable=True) # Linked if possible