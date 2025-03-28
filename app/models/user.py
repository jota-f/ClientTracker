from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict
from typing import List, Optional, Dict, Any, Annotated
from datetime import datetime, timezone
from enum import Enum
from bson import ObjectId
from pydantic_core import core_schema
from pydantic.json_schema import JsonSchemaValue
from app.models.notification_settings import NotificationSettings, NotificationPreference

class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Any,
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.chain_schema([
                core_schema.union_schema([
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.str_schema(),
                ]),
                core_schema.no_info_plain_validator_function(cls.validate),
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x) if isinstance(x, ObjectId) else x
            ),
        )

    @classmethod
    def validate(cls, value: Any) -> str:
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, str) and ObjectId.is_valid(value):
            return value
        raise ValueError("Invalid ObjectId")

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        _core_schema: core_schema.CoreSchema,
        _handler: Any
    ) -> JsonSchemaValue:
        return {
            "type": "string",
            "examples": ["507f1f77bcf86cd799439011"]
        }

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class CalendarIntegrationType(str, Enum):
    GOOGLE = "google"
    OUTLOOK = "outlook"
    NONE = "none"

class CalendarIntegration(BaseModel):
    type: CalendarIntegrationType = CalendarIntegrationType.NONE
    enabled: bool = False
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None

    @validator('expires_at')
    def ensure_timezone(cls, v):
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )

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
    notification_settings: NotificationSettings = Field(default_factory=NotificationSettings)

    @validator('created_at', 'updated_at', 'last_login')
    def ensure_timezone(cls, v):
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            ObjectId: str
        },
        use_enum_values=True
    )

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
    notification_settings: NotificationSettings = Field(default_factory=NotificationSettings)

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    notification_preference: Optional[NotificationPreference] = None
    notification_settings: Optional[NotificationSettings] = None
    
class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str 