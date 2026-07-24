import uuid

from pydantic import BaseModel, Field


class WorkflowTemplateStageIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: str


class WorkflowTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    stages: list[WorkflowTemplateStageIn]


class WorkflowTemplateStageOut(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    sort: int


class WorkflowTemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    stages: list[WorkflowTemplateStageOut]
