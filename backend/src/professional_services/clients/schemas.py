import uuid

from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(default="person", pattern="^(person|company)$")


class ClientOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
