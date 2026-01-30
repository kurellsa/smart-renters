from pydantic import BaseModel, Field
from typing import List, Optional

class PropertyItem(BaseModel):
    address: str 
    rent_amount: float 
    rent_paid: float
    management_fees: float
    net_income: float

class ExtractedDoc(BaseModel):
    # This must match your LLM output keys
    statement_date: str
    merchant_group: str
    properties: List[PropertyItem]

    class Config:
        populate_by_name = True