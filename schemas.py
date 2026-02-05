# backend/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

#-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
#       Todo Schemas
#-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-

class TodoBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: Optional[str] = "low"
    category: Optional[str] = "others"

class TodoCreate(TodoBase):
    pass

class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    category: Optional[str] = None


class TodoResponse(TodoBase):
    id: int
    completed: bool
    created_at: datetime
    updated_at: datetime
    owner_id: int
    priority: str
    category: str

    class Config:
        from_attributes = True # Enable ORM mode

#-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
#       User Schemas
#-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-

class UserBase(BaseModel):
    username: str = Field(..., max_length=50)
    email: str = Field(..., max_length=100)

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    todos: List[TodoResponse] = []

    class Config:
        from_attributes = True # Enable ORM mode

class UserWithToken(UserResponse):
    access_token: str
    token_type: str

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, max_length=50)

class PasswordReset(BaseModel):
    current_password: str
    new_password: str

class UserDelete(BaseModel):
    password: str

#-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
#       Token Schemas
#-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class ForgotPassword(BaseModel):
    email: str

class ResetPassword(BaseModel):
    new_password: str


#-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
#       Dashboard Schemas
#-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-

class TaskStats(BaseModel):
    total: int
    completed: int
    in_progress: int
    overdue: int

class PriorityStat(BaseModel):
    priority: str
    count: int

class CategoryStat(BaseModel):
    category: str
    count: int
    
class DeadlineStat(BaseModel):
    id: int
    title: str
    due_at: datetime
    
    class Config:
        from_attributes = True

class DashboardStats(BaseModel):
    stats: TaskStats
    priorities: List[PriorityStat]
    categories: List[CategoryStat]
    deadlines: List[DeadlineStat]