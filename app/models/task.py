from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum
from bson import ObjectId
from app.models.client import PyObjectId

class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    ARCHIVED = "ARCHIVED"

class TaskPriority(str, Enum):
    URGENT_IMPORTANT = "URGENT_IMPORTANT"     # Quadrante 1: Urgente e Importante
    NOT_URGENT_IMPORTANT = "NOT_URGENT_IMPORTANT"   # Quadrante 2: Não Urgente e Importante
    URGENT_NOT_IMPORTANT = "URGENT_NOT_IMPORTANT"   # Quadrante 3: Urgente e Não Importante
    NOT_URGENT_NOT_IMPORTANT = "NOT_URGENT_NOT_IMPORTANT"   # Quadrante 4: Não Urgente e Não Importante

class TaskComment(BaseModel):
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @validator('created_at')
    def ensure_timezone(cls, v):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    
    class Config:
        populate_by_name = True

class Task(BaseModel):
    id: Optional[PyObjectId] = Field(alias='_id')
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority
    due_date: Optional[datetime] = None
    client_id: Optional[PyObjectId] = None
    client_name: Optional[str] = None  # Para facilitar a exibição
    assignee: Optional[str] = None
    user_id: Optional[str] = None  # ID do usuário proprietário da tarefa
    comments: List[TaskComment] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @validator('due_date', 'created_at', 'updated_at')
    def ensure_timezone(cls, v):
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ObjectId: str
        }
        use_enum_values = True 