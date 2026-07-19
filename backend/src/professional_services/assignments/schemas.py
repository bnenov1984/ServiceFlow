import uuid
from datetime import date

from pydantic import BaseModel, Field


class AssignmentCreate(BaseModel):
    client_id: uuid.UUID
    title: str = Field(min_length=1, max_length=300)
    official_deadline_on: date | None = None
    internal_target_on: date | None = None


class StageChange(BaseModel):
    to: str


class AssignmentOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    title: str
    stage: str
    lifecycle_state: str
    official_deadline_on: date | None
    internal_target_on: date | None
