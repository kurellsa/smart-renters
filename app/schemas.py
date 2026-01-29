from pydantic import BaseModel
from typing import Optional, List

class ExtractedDoc(BaseModel):
    date: Optional[str]
    address: Optional[str]
    rent: Optional[float]
    fees: Optional[float]
    net_income: Optional[float]
    
class ReconciliationResult(BaseModel):
    property_id: Optional[str]
    rent_match: bool
    fee_match: bool
    differences: List[dict]
    net: Optional[float]