from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

class InviteRequest(BaseModel):
    id: Optional[str] = Field(alias='_id', default=None)
    name: str
    email: EmailStr
    company: str
    status: str = "pending"  # pending, approved, rejected
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    processed_by: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            ObjectId: str
        }
    )

class InviteRequestCreate(BaseModel):
    name: str
    email: EmailStr
    company: str
