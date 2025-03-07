from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum
from bson import ObjectId

class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v

class ClientStatus(str, Enum):
    LEAD = "LEAD"
    OPPORTUNITY = "OPPORTUNITY"
    CUSTOMER = "CUSTOMER"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class RFMScores(BaseModel):
    recency: int = Field(ge=1, le=5)
    potential: int = Field(ge=1, le=5)
    engagement: int = Field(ge=0, le=5)
    total: int = Field(ge=2, le=15)

    class Config:
        allow_population_by_field_name = True

class Interaction(BaseModel):
    date: datetime
    type: str
    notes: str
    outcome: Optional[str] = None

    @validator('date')
    def ensure_timezone(cls, v):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    class Config:
        allow_population_by_field_name = True

class Task(BaseModel):
    title: str
    due_date: datetime
    status: str
    description: Optional[str] = None

    @validator('due_date')
    def ensure_timezone(cls, v):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    class Config:
        allow_population_by_field_name = True

class Client(BaseModel):
    id: Optional[PyObjectId] = Field(alias='_id')
    name: str
    company: str
    email: str
    phone: str
    status: ClientStatus
    sales_potential: int = Field(ge=1, le=5)
    last_contact: datetime
    next_followup: datetime
    interaction_history: List[Interaction] = []
    pending_tasks: List[Task] = []
    rfm_scores: Optional[RFMScores] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @validator('last_contact', 'next_followup', 'created_at', 'updated_at')
    def ensure_timezone(cls, v):
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ObjectId: str
        }
        use_enum_values = True 