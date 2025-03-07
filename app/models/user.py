from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Dict
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

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class CalendarIntegrationType(str, Enum):
    GOOGLE = "google"
    OUTLOOK = "outlook"
    NONE = "none"

class NotificationPreference(str, Enum):
    EMAIL = "email"
    IN_APP = "in_app"
    BOTH = "both"
    NONE = "none"

class CalendarIntegration(BaseModel):
    type: CalendarIntegrationType
    enabled: bool = False
    auth_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    calendar_id: Optional[str] = None

    @validator('expires_at')
    def ensure_timezone(cls, v):
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class User(BaseModel):
    id: Optional[PyObjectId] = Field(alias='_id')
    username: str
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    notification_preference: NotificationPreference = NotificationPreference.EMAIL
    calendar_integration: CalendarIntegration = Field(
        default_factory=lambda: CalendarIntegration(type=CalendarIntegrationType.NONE)
    )
    email_verified: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    @validator('created_at', 'updated_at', 'last_login')
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

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    notification_preference: str
    calendar_integration: CalendarIntegration
    email_verified: bool
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    notification_preference: Optional[NotificationPreference] = None
    
class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str 