"""
Pydantic схемы для шаблонов сообщений.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# DefaultMessage
# ------------------------------------------------------------------

class DefaultMessageUpdate(BaseModel):
    message: str = Field(..., min_length=1)


class DefaultMessageResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    avito_account_id: uuid.UUID
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# ItemMessage
# ------------------------------------------------------------------

class ItemMessageUpdate(BaseModel):
    avito_account_id: uuid.UUID
    message: str = Field(..., min_length=1)


class ItemMessageResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    avito_account_id: uuid.UUID
    avito_item_id: int
    message: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# AutoResponseRule
# ------------------------------------------------------------------

class AutoResponseRuleCreate(BaseModel):
    avito_account_id: uuid.UUID
    avito_item_id: int | None = None
    auto_type: str = Field(default="on_response", max_length=50)
    is_active: bool = True


class AutoResponseRulePatch(BaseModel):
    avito_item_id: int | None = None
    auto_type: str | None = None
    is_active: bool | None = None


class AutoResponseRuleResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    avito_account_id: uuid.UUID
    avito_item_id: int | None
    auto_type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# FastAnswer
# ------------------------------------------------------------------

class FastAnswerCreate(BaseModel):
    message: str = Field(..., min_length=1)
    sort_order: int = 0


class FastAnswerPatch(BaseModel):
    message: str | None = None
    sort_order: int | None = None


class FastAnswerReorder(BaseModel):
    ordered_ids: list[uuid.UUID] = Field(..., min_length=1)


class FastAnswerResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    message: str
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}
