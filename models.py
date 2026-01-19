from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime

class Group(SQLModel, table=True):
    # WhatsApp JID or LID
    id: str = Field(primary_key=True) 
    platform: str = "whatsapp"
    admin_id: str 
    is_active: bool = True
    
    tasks: List["Task"] = Relationship(back_populates="group")

class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    
    # 🚀 ADD THIS FIELD:
    store: str = Field(default="General", index=True) 
    
    # 🚀 ADD THIS FIELD (Recommended for sorting/history):
    created_at: datetime = Field(default_factory=datetime.now)

    assigned_to: Optional[str] = None
    due_at: Optional[datetime] = None
    
    group_id: str = Field(foreign_key="group.id")
    group: Group = Relationship(back_populates="tasks")