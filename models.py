from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime

class Group(SQLModel, table=True):
    # WhatsApp JID or LID (e.g., '12345@g.us' or '67890@lid')
    id: str = Field(primary_key=True) 
    platform: str = "whatsapp"
    admin_id: str               # The ID of the user who can 'Clear All'
    is_active: bool = True
    
    # Relationship: One Group can have many Tasks
    tasks: List["Task"] = Relationship(back_populates="group")

class Task(SQLModel, table=True):
    # Auto-incrementing internal ID for the database
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    assigned_to: Optional[str] = None
    due_at: Optional[datetime] = None
    
    # Foreign Key: Connects the task to a specific Group ID
    group_id: str = Field(foreign_key="group.id")
    
    # Relationship: Each task belongs to one Group
    group: Group = Relationship(back_populates="tasks")