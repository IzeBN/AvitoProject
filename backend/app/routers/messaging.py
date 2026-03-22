"""
Роутер управления шаблонами сообщений:
item_messages, auto_response_rules.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.auth import User
from app.models.messaging import AutoResponseRule
from app.repositories.messaging import MessagingRepository
from app.schemas.messaging import (
    AutoResponseRuleCreate,
    AutoResponseRulePatch,
    AutoResponseRuleResponse,
    ItemMessageResponse,
    ItemMessageUpdate,
)

router = APIRouter(prefix="/messaging", tags=["messaging"])


def _repo(db: AsyncSession) -> MessagingRepository:
    return MessagingRepository(db)


# ------------------------------------------------------------------
# Item Messages
# ------------------------------------------------------------------

@router.get("/items", response_model=list[ItemMessageResponse])
async def list_item_messages(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ItemMessageResponse]:
    items = await _repo(db).get_item_messages(current_user.org_id)
    return [ItemMessageResponse.model_validate(i) for i in items]


@router.put("/items/{item_id}", response_model=ItemMessageResponse)
async def upsert_item_message(
    item_id: int,
    body: ItemMessageUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ItemMessageResponse:
    msg = await _repo(db).upsert_item_message(
        current_user.org_id, body.avito_account_id, item_id, body.message
    )
    await db.commit()
    await db.refresh(msg)
    return ItemMessageResponse.model_validate(msg)


# ------------------------------------------------------------------
# Auto-Response Rules
# ------------------------------------------------------------------

@router.get("/auto-response", response_model=list[AutoResponseRuleResponse])
async def list_auto_rules(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AutoResponseRuleResponse]:
    rules = await _repo(db).get_auto_rules(current_user.org_id)
    return [AutoResponseRuleResponse.model_validate(r) for r in rules]


@router.post(
    "/auto-response",
    response_model=AutoResponseRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_auto_rule(
    body: AutoResponseRuleCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AutoResponseRuleResponse:
    rule = AutoResponseRule(
        org_id=current_user.org_id,
        avito_account_id=body.avito_account_id,
        avito_item_ids=body.avito_item_ids,
        message=body.message,
        auto_type=body.auto_type,
        is_active=body.is_active,
    )
    rule = await _repo(db).create_auto_rule(rule)
    await db.commit()
    await db.refresh(rule)
    return AutoResponseRuleResponse.model_validate(rule)


@router.patch("/auto-response/{rule_id}", response_model=AutoResponseRuleResponse)
async def patch_auto_rule(
    rule_id: uuid.UUID,
    body: AutoResponseRulePatch,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AutoResponseRuleResponse:
    rule = await _repo(db).get_auto_rule_by_id(current_user.org_id, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Правило не найдено")

    if body.avito_item_ids is not None:
        rule.avito_item_ids = body.avito_item_ids
    if body.message is not None:
        rule.message = body.message
    if body.auto_type is not None:
        rule.auto_type = body.auto_type
    if body.is_active is not None:
        rule.is_active = body.is_active

    await db.commit()
    await db.refresh(rule)
    return AutoResponseRuleResponse.model_validate(rule)


@router.delete(
    "/auto-response/{rule_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_auto_rule(
    rule_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    rule = await _repo(db).get_auto_rule_by_id(current_user.org_id, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    await _repo(db).delete_auto_rule(rule)
    await db.commit()
