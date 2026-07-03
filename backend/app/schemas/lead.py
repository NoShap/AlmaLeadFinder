import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.lead import LeadState


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    resume_filename: str
    state: LeadState
    created_at: datetime
    updated_at: datetime
    reached_out_at: datetime | None


class LeadList(BaseModel):
    items: list[LeadRead]
    total: int


class LeadStateUpdate(BaseModel):
    state: LeadState
