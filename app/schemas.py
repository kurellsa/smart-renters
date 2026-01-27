from pydantic import BaseModel
from typing import Optional, List

class ExtractedDoc(BaseModel):
    property_id: Optional[str]
    period: Optional[str]
    rent: Optional[float]
    fees: Optional[float]

class ReconciliationResult(BaseModel):
    property_id: Optional[str]
    rent_match: bool
    fee_match: bool
    differences: List[dict]
    net: Optional[float]