"""
Роутер управления шаблонами сообщений:
default_messages, item_messages, auto_response_rules, fast_answers.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.auth import User
from app.models.messaging import AutoResponseRule
from app.models.chat import FastAnswer
from app.repositories.messaging import MessagingRepository
from app.schemas.messaging import (
    AutoResponseRuleCreate,
    AutoResponseRulePatch,
    AutoResponseRuleResponse,
    DefaultMessageResponse,
    DefaultMessageUpdate,
    FastAnswerCreate,
    FastAnswerPatch,
    FastAnswerReorder,
    FastAnswerResponse,
    ItemMessageResponse,
    ItemMessageUpdate,
)

router = APIRouter(prefix="/messaging", tags=["messaging"])


def _repo(db: AsyncSession) -> MessagingRepository:
    return MessagingRepository(db)


# ------------------------------------------------------------------
# Default Messages
# ------------------------------------------------------------------

@router.get(
    "/default/{account_id}",
    response_model=DefaultMessageResponse,
)
async def get_default_message(
    account_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DefaultMessageResponse:
    msg = await _repo(db).get_default_message(current_user.org_id, account_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Дефолтное сообщение не найдено")
    return DefaultMessageResponse.model_validate(msg)


@router.put(
    "/default/{account_id}",
    response_model=DefaultMessageResponse,
)
async def upsert_default_message(
    account_id: uuid.UUID,
    body: DefaultMessageUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DefaultMessageResponse:
    msg = await _repo(db).upsert_default_message(
        current_user.org_id, account_id, body.message
    )
    await db.commit()
    await db.refresh(msg)
    return DefaultMessageResponse.model_validate(msg)


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
        avito_item_id=body.avito_item_id,
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

    if body.avito_item_id is not None:
        rule.avito_item_id = body.avito_item_id
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


# ------------------------------------------------------------------
# Fast Answers
# ------------------------------------------------------------------

@router.get("/fast-answers", response_model=list[FastAnswerResponse])
async def list_fast_answers(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[FastAnswerResponse]:
    answers = await _repo(db).get_fast_answers(current_user.org_id, current_user.id)
    return [FastAnswerResponse.model_validate(a) for a in answers]


@router.post(
    "/fast-answers",
    response_model=FastAnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_fast_answer(
    body: FastAnswerCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FastAnswerResponse:
    answer = FastAnswer(
        org_id=current_user.org_id,
        user_id=current_user.id,
        message=body.message,
        sort_order=body.sort_order,
    )
    answer = await _repo(db).create_fast_answer(answer)
    await db.commit()
    await db.refresh(answer)
    return FastAnswerResponse.model_validate(answer)


@router.patch("/fast-answers/{answer_id}", response_model=FastAnswerResponse)
async def patch_fast_answer(
    answer_id: uuid.UUID,
    body: FastAnswerPatch,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FastAnswerResponse:
    answer = await _repo(db).get_fast_answer_by_id(
        current_user.org_id, current_user.id, answer_id
    )
    if answer is None:
        raise HTTPException(status_code=404, detail="Быстрый ответ не найден")

    if body.message is not None:
        answer.message = body.message
    if body.sort_order is not None:
        answer.sort_order = body.sort_order

    await db.commit()
    await db.refresh(answer)
    return FastAnswerResponse.model_validate(answer)


@router.delete(
    "/fast-answers/{answer_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_fast_answer(
    answer_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    answer = await _repo(db).get_fast_answer_by_id(
        current_user.org_id, current_user.id, answer_id
    )
    if answer is None:
        raise HTTPException(status_code=404, detail="Быстрый ответ не найден")
    await _repo(db).delete_fast_answer(answer)
    await db.commit()


@router.put("/fast-answers/reorder", response_model=list[FastAnswerResponse])
async def reorder_fast_answers(
    body: FastAnswerReorder,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[FastAnswerResponse]:
    """Переупорядочить быстрые ответы по списку IDs."""
    repo = _repo(db)
    answers = await repo.get_fast_answers(current_user.org_id, current_user.id)
    answer_map = {a.id: a for a in answers}

    for idx, aid in enumerate(body.ordered_ids):
        if aid in answer_map:
            answer_map[aid].sort_order = idx

    await db.commit()
    updated = await repo.get_fast_answers(current_user.org_id, current_user.id)
    return [FastAnswerResponse.model_validate(a) for a in updated]
