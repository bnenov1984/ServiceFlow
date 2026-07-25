import uuid
from datetime import date, datetime

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


class DeadlineChangeIn(BaseModel):
    official_deadline_on: date
    reason: str = Field(min_length=1, max_length=500)


class DeadlineChangeOut(BaseModel):
    old_value: date | None
    new_value: date
    reason: str
    changed_at: datetime


class AssignmentOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    title: str
    lifecycle_state: str
    current_stage: StageOut | None
    official_deadline_on: date | None
    internal_target_on: date | None
    current_deadline_risk: str
    current_stale: bool
