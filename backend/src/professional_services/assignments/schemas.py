import uuid
from datetime import date

from pydantic import BaseModel, Field


class AssignmentCreate(BaseModel):
    client_id: uuid.UUID
    title: str = Field(min_length=1, max_length=300)
    official_deadline_on: date | None = None
    internal_target_on: date | None = None
    workflow_template_id: uuid.UUID | None = None


class StageChange(BaseModel):
    to_stage_id: uuid.UUID


class StageOut(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    sort: int


class AssignmentOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    title: str
    lifecycle_state: str
    current_stage: StageOut | None
    official_deadline_on: date | None
    internal_target_on: date | None
