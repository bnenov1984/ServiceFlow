import uuid
from datetime import date

from pydantic import BaseModel, Field


class NextActionCreate(BaseModel):
    assignment_id: uuid.UUID
    title: str = Field(min_length=1, max_length=300)
    owner_user_id: uuid.UUID
    due_on: date


class NextActionOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    title: str
    owner_user_id: uuid.UUID
    due_on: date
    completed: bool
    risk: str
