from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date as DateType

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
    class Config:
        populate_by_name = True

class RentalStatementOut(BaseModel):
    id: int
    statement_date: DateType
    property_management: Optional[str]
    address: Optional[str]
    rent_amount: Optional[float]
    rent_paid: Optional[float]
    management_fees: Optional[float]
    net_income: Optional[float]
    source_file: Optional[str]

    class Config:
        from_attributes = True