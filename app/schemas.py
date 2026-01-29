from pydantic import BaseModel, Field
from typing import List, Optional

class PropertyItem(BaseModel):
    # This allows the LLM to use "address" as the key
    address: str 
    rent: float
    # This allows the LLM to use "fee" but saves it as "fees"
    fees: float = Field(0.0, alias="fee") 

class ExtractedDoc(BaseModel):
    # This captures the list of properties
    properties: List[PropertyItem]
    # This captures "statement_date" but saves it as "date"
    date: Optional[str] = Field(None, alias="statement_date")
    net_income: Optional[float] = None

    class Config:
        populate_by_name = True