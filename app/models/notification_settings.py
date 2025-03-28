from enum import Enum
from pydantic import BaseModel, ConfigDict

class NotificationPreference(str, Enum):
    EMAIL = "email"
    IN_APP = "in_app"
    BOTH = "both"
    NONE = "none"

class NotificationSettings(BaseModel):
    rfm_reminders: bool = True
    task_reminders: bool = True
    followup_reminders: bool = True
    
    model_config = ConfigDict(
        json_encoders={bool: bool},
        populate_by_name=True,
        use_enum_values=True
    ) 