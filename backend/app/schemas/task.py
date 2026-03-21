"""
Схемы Pydantic для задач.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(..., max_length=500)
    description: str | None = None
    due_date: str | None = None  # ISO date string "YYYY-MM-DD"
    priority: str = "medium"  # low | medium | high
    status: str = "open"       # open | in_progress | done
    responsible_id: uuid.UUID | None = None
    candidate_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(None, max_length=500)
    description: str | None = None
    due_date: str | None = None
    priority: str | None = None
    status: str | None = None
    responsible_id: uuid.UUID | None = None
    candidate_id: uuid.UUID | None = None


class AssigneeInfo(BaseModel):
    id: uuid.UUID
    full_name: str


class CandidateInfo(BaseModel):
    id: uuid.UUID
    name: str | None


class TaskResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    description: str | None
    due_date: str | None  # "YYYY-MM-DD" or None
    priority: str
    status: str
    assignee: AssigneeInfo | None
    candidate: CandidateInfo | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int
    pages: int


class TaskFilters(BaseModel):
    responsible_id: uuid.UUID | None = None
    candidate_id: uuid.UUID | None = None
    status: str | None = None
