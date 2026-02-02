from pydantic import BaseModel, Field
from typing import List, Optional

class PropertyItem(BaseModel):
    address: str = Field(default="Unknown Address")
    rent_amount: float = Field(default=0.0)
    rent_paid: float = Field(default=0.0)
    management_fees: float = Field(default=0.0)
    net_income: float = Field(default=0.0)
class ExtractedDoc(BaseModel):
    # This must match your LLM output keys
    statement_date: str
    merchant_group: str
    properties: List[PropertyItem] = Field(default_factory=list)

    class Config:
        populate_by_name = True