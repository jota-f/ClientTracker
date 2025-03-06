from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class Client(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    company: str
    last_contact: datetime
    next_followup: datetime
    sales_potential: int  # Scale from 1 to 5
    status: str
    pending_tasks: List[str] = []
    interaction_history: List[str] = [] 