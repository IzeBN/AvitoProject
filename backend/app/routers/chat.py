"""
Роутер чата.

GET  /api/v1/chat/list                       — список чатов (ChatMetadata) для орг.
GET  /api/v1/chat/{candidate_id}/messages    — история сообщений (cursor-пагинация)
POST /api/v1/chat/{candidate_id}/send        — отправить сообщение через Avito API
POST /api/v1/chat/{candidate_id}/read        — отметить прочитанным (write-behind)

GET    /api/v1/chat/fast-answers             — список быстрых ответов
POST   /api/v1/chat/fast-answers             — создать быстрый ответ
PATCH  /api/v1/chat/fast-answers/{id}        — обновить
DELETE /api/v1/chat/fast-answers/{id}        — удалить
POST   /api/v1/chat/fast-answers/reorder     — переупорядочить

GET  /api/v1/chats                           — алиас для list (legacy)
GET  /api/v1/chats/{candidate_id}            — алиас для messages (legacy)
POST /api/v1/chats/{candidate_id}/read       — алиас для read (legacy)
GET  /api/v1/filters                         — значения для фильтров
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.auth import User
from app.models.avito import AvitoAccount
from app.models.chat import ChatMessage, ChatMetadata, FastAnswer
from app.models.crm import Candidate
from app.redis import get_redis
from app.repositories.chat import ChatRepository
from app.schemas.chat import (
    ChatListResponse,
    ChatMessageResponse,
    ChatMessagesResponse,
    FastAnswerCreate,
    FastAnswerReorderRequest,
    FastAnswerResponse,
    FastAnswerUpdate,
    FilterOptionsResponse,
    SendMessageRequest,
)
from app.services.avito_client import AvitoAPIClient
from app.services.cache import CacheService
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _get_chat_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ChatService:
    return ChatService(
        repo=ChatRepository(db),
        cache=CacheService(redis),
    )


def _get_avito_client(request: Request) -> AvitoAPIClient:
    return request.app.state.avito_client


# ===========================================================================
# Chat list
# ===========================================================================


@router.get(
    "/chat/list",
    response_model=ChatListResponse,
    summary="Список чатов организации",
    description=(
        "Возвращает чаты отсортированные по last_message_at DESC. "
        "unread_count берётся из Redis write-behind или БД."
    ),
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def chat_list(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(default=None, max_length=255),
    has_unread: bool | None = Query(default=None),
    avito_account_id: uuid.UUID | None = Query(default=None),
    stage_id: uuid.UUID | None = Query(default=None),
    responsible_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
) -> ChatListResponse:
    """Список чатов с фильтрацией и пагинацией."""
    org_id: uuid.UUID = request.state.org_id
    cache = CacheService(redis)

    # Строим запрос
    conditions = [
        ChatMetadata.org_id == org_id,
        Candidate.deleted_at.is_(None),
    ]

    if search:
        conditions.append(Candidate.name.ilike(f"%{search}%"))

    if has_unread is True:
        conditions.append(ChatMetadata.unread_count > 0)
    elif has_unread is False:
        conditions.append(ChatMetadata.unread_count == 0)

    if avito_account_id:
        conditions.append(Candidate.avito_account_id == avito_account_id)

    if stage_id:
        conditions.append(Candidate.stage_id == stage_id)

    if responsible_id:
        conditions.append(Candidate.responsible_id == responsible_id)

    count_stmt = (
        select(func.count(ChatMetadata.id))
        .join(Candidate, Candidate.id == ChatMetadata.candidate_id)
        .where(and_(*conditions))
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    offset = (page - 1) * per_page
    stmt = (
        select(ChatMetadata, Candidate.name.label("candidate_name"))
        .join(Candidate, Candidate.id == ChatMetadata.candidate_id)
        .where(and_(*conditions))
        .order_by(func.coalesce(ChatMetadata.last_message_at, ChatMetadata.updated_at).desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for row in rows:
        meta: ChatMetadata = row[0]
        candidate_name: str | None = row[1]

        # Читаем актуальные данные из Redis write-behind (ещё не сброшены в БД)
        wb_key = f"wb:chat_meta:{meta.chat_id}"
        wb_raw = await redis.hgetall(wb_key)
        wb: dict[str, str] = {
            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in (wb_raw or {}).items()
        }

        unread_count = meta.unread_count
        if "unread_count" in wb:
            try:
                unread_count = int(wb["unread_count"])
            except (ValueError, TypeError):
                pass

        last_message = meta.last_message
        if wb.get("last_message"):
            last_message = wb["last_message"]

        last_message_at = meta.last_message_at
        if wb.get("last_message_at"):
            try:
                from datetime import datetime as _dt
                wb_at = _dt.fromisoformat(wb["last_message_at"])
                if last_message_at is None or wb_at > last_message_at:
                    last_message_at = wb_at
            except (ValueError, TypeError):
                pass

        items.append(
            {
                "candidate_id": meta.candidate_id,
                "chat_id": meta.chat_id,
                "candidate_name": candidate_name,
                "last_message": last_message,
                "last_message_at": last_message_at,
                "unread_count": unread_count,
                "is_blocked": meta.is_blocked,
            }
        )

    import math
    from app.schemas.chat import ChatListItem

    pages = max(1, math.ceil(total / per_page)) if per_page > 0 else 1
    return ChatListResponse(
        items=[ChatListItem(**item) for item in items],
        total=total,
        page=page,
        page_size=per_page,
        pages=pages,
    )


# ===========================================================================
# Fast answers — ВАЖНО: статичные маршруты должны быть ДО /{candidate_id}
# ===========================================================================


@router.get(
    "/chat/fast-answers",
    response_model=list[FastAnswerResponse],
    summary="Список быстрых ответов",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def list_fast_answers(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> list[FastAnswerResponse]:
    """Быстрые ответы организации, отсортированные по sort_order."""
    org_id: uuid.UUID = request.state.org_id
    result = await db.execute(
        select(FastAnswer)
        .where(FastAnswer.org_id == org_id)
        .order_by(FastAnswer.sort_order.asc(), FastAnswer.created_at.asc())
    )
    answers = result.scalars().all()
    return [FastAnswerResponse.model_validate(a) for a in answers]


@router.post(
    "/chat/fast-answers",
    response_model=FastAnswerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать быстрый ответ",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def create_fast_answer(
    data: FastAnswerCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> FastAnswerResponse:
    org_id: uuid.UUID = request.state.org_id
    answer = FastAnswer(
        org_id=org_id,
        title=data.title,
        text=data.text,
        sort_order=data.sort_order,
    )
    db.add(answer)
    await db.flush()
    await db.refresh(answer)
    await db.commit()
    return FastAnswerResponse.model_validate(answer)


@router.post(
    "/chat/fast-answers/reorder",
    status_code=status.HTTP_200_OK,
    summary="Переупорядочить быстрые ответы",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def reorder_fast_answers(
    data: FastAnswerReorderRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    org_id: uuid.UUID = request.state.org_id
    for item in data.items:
        await db.execute(
            update(FastAnswer)
            .where(FastAnswer.id == item.id, FastAnswer.org_id == org_id)
            .values(sort_order=item.sort_order)
        )
    await db.commit()


@router.patch(
    "/chat/fast-answers/{answer_id}",
    response_model=FastAnswerResponse,
    summary="Обновить быстрый ответ",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def update_fast_answer(
    answer_id: uuid.UUID,
    data: FastAnswerUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> FastAnswerResponse:
    org_id: uuid.UUID = request.state.org_id
    result = await db.execute(
        select(FastAnswer).where(
            FastAnswer.id == answer_id, FastAnswer.org_id == org_id
        )
    )
    answer = result.scalar_one_or_none()
    if answer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Быстрый ответ не найден",
        )
    update_data = data.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(answer, key, value)
    db.add(answer)
    await db.flush()
    await db.refresh(answer)
    await db.commit()
    return FastAnswerResponse.model_validate(answer)


@router.delete(
    "/chat/fast-answers/{answer_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить быстрый ответ",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def delete_fast_answer(
    answer_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    org_id: uuid.UUID = request.state.org_id
    result = await db.execute(
        select(FastAnswer).where(
            FastAnswer.id == answer_id, FastAnswer.org_id == org_id
        )
    )
    answer = result.scalar_one_or_none()
    if answer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Быстрый ответ не найден",
        )
    await db.delete(answer)
    await db.commit()


# ===========================================================================
# Message history
# ===========================================================================


@router.get(
    "/chat/{candidate_id}/messages",
    response_model=ChatMessagesResponse,
    summary="История сообщений кандидата (cursor-пагинация)",
    description=(
        "Возвращает сообщения в хронологическом порядке. "
        "Для подгрузки более ранних сообщений передайте before_id = UUID первого "
        "сообщения в текущей порции. "
        "Кеширование: TTL 120 сек, ключ org:{org_id}:chat:{candidate_id}:page:{cursor}."
    ),
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_messages(
    candidate_id: uuid.UUID,
    request: Request,
    service: Annotated[ChatService, Depends(_get_chat_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
    before_id: uuid.UUID | None = Query(
        default=None,
        description="UUID сообщения — загрузить сообщения раньше этого",
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> ChatMessagesResponse:
    """
    История сообщений с cursor-пагинацией по UUID.
    Если before_id не указан — возвращает последние limit сообщений.
    """
    org_id: uuid.UUID = request.state.org_id

    # Конвертируем before_id → before_cursor (ISO datetime)
    before_cursor: str | None = None
    if before_id is not None:
        from app.database import get_db as _get_db

        # Ищем created_at для указанного сообщения чтобы использовать как cursor
        from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

        db_session: _AsyncSession = request.state.db if hasattr(request.state, "db") else None  # type: ignore[assignment]
        # Fallback — используем DI сессию через фабрику
        from app.database import get_session_factory

        factory = get_session_factory()
        async with factory() as tmp_session:
            msg_result = await tmp_session.execute(
                select(ChatMessage.created_at).where(ChatMessage.id == before_id)
            )
            msg_created_at = msg_result.scalar_one_or_none()
            if msg_created_at:
                before_cursor = msg_created_at.isoformat()

    return await service.get_messages(request, candidate_id, limit, before_cursor)


# ===========================================================================
# Send message
# ===========================================================================


@router.post(
    "/chat/{candidate_id}/send",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Отправить сообщение кандидату",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def send_message(
    candidate_id: uuid.UUID,
    body: SendMessageRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    current_user: Annotated[User, Depends(get_current_user)],
    avito_client: Annotated[AvitoAPIClient, Depends(_get_avito_client)],
) -> ChatMessageResponse:
    """
    Отправить текстовое сообщение через Avito API.
    Сохраняет в chat_messages, обновляет ChatMetadata.
    """
    org_id: uuid.UUID = request.state.org_id

    # Загружаем метаданные чата
    meta_result = await db.execute(
        select(ChatMetadata).where(
            ChatMetadata.candidate_id == candidate_id,
            ChatMetadata.org_id == org_id,
        )
    )
    meta = meta_result.scalar_one_or_none()
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат для данного кандидата не найден",
        )

    if meta.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Кандидат заблокирован",
        )

    # Загружаем Avito аккаунт кандидата
    cand_result = await db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.org_id == org_id,
        )
    )
    candidate = cand_result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кандидат не найден",
        )

    account_result = await db.execute(
        select(AvitoAccount).where(
            AvitoAccount.id == candidate.avito_account_id,
            AvitoAccount.org_id == org_id,
            AvitoAccount.is_active.is_(True),
        )
    )
    account = account_result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avito аккаунт не найден или неактивен",
        )

    # Отправляем через Avito API
    try:
        await avito_client.send_message(
            account=account,
            chat_id=meta.chat_id,
            user_id=account.avito_user_id,
            text=body.text,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка отправки через Avito API: {exc}",
        ) from exc

    # Сохраняем в БД
    preview = body.text[:100] if body.text else ""
    now = datetime.now(timezone.utc)

    message = ChatMessage(
        org_id=org_id,
        candidate_id=candidate_id,
        chat_id=meta.chat_id,
        author_type="account",
        message_type="text",
        content=body.text,
        is_read=True,
        created_at=now,
    )
    db.add(message)
    await db.flush()

    # Авто-назначение ответственного: если ещё не назначен — ставим текущего пользователя
    if candidate.responsible_id is None:
        await db.execute(
            update(Candidate)
            .where(Candidate.id == candidate_id)
            .values(responsible_id=current_user.id)
        )

    # Обновляем метаданные чата
    await db.execute(
        update(ChatMetadata)
        .where(ChatMetadata.id == meta.id)
        .values(
            last_message=preview,
            last_message_at=now,
        )
    )

    await db.commit()
    await db.refresh(message)

    # Инвалидируем кеш сообщений
    cache = CacheService(redis)
    await cache.invalidate_chat(str(candidate_id))

    return ChatMessageResponse(
        id=message.id,
        chat_id=message.chat_id,
        candidate_id=candidate_id,
        author_type=message.author_type,
        message_type=message.message_type,
        content=message.content,
        avito_message_id=message.avito_message_id,
        is_read=message.is_read,
        created_at=message.created_at,
    )


# ===========================================================================
# Sync messages from Avito
# ===========================================================================


@router.post(
    "/chat/{candidate_id}/sync",
    status_code=status.HTTP_200_OK,
    summary="Синхронизировать историю сообщений из Avito",
    description="Загружает историю сообщений из Avito API и сохраняет новые в БД.",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def sync_messages(
    candidate_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    avito_client: Annotated[AvitoAPIClient, Depends(_get_avito_client)],
) -> dict:
    """
    Получает историю чата из Avito API и делает upsert новых сообщений в chat_messages.
    Возвращает количество добавленных сообщений.
    """
    org_id: uuid.UUID = request.state.org_id

    # Загружаем метаданные чата
    meta_result = await db.execute(
        select(ChatMetadata).where(
            ChatMetadata.candidate_id == candidate_id,
            ChatMetadata.org_id == org_id,
        )
    )
    meta = meta_result.scalar_one_or_none()
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат для данного кандидата не найден",
        )

    # Загружаем кандидата для получения аккаунта
    cand_result = await db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.org_id == org_id,
        )
    )
    candidate = cand_result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кандидат не найден",
        )

    account_result = await db.execute(
        select(AvitoAccount).where(
            AvitoAccount.id == candidate.avito_account_id,
            AvitoAccount.org_id == org_id,
            AvitoAccount.is_active.is_(True),
        )
    )
    account = account_result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avito аккаунт не найден или неактивен",
        )

    # Получаем историю из Avito API
    try:
        messages = await avito_client.get_messages(
            account=account,
            chat_id=meta.chat_id,
            user_id=account.avito_user_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка получения сообщений из Avito API: {exc}",
        ) from exc

    added = 0
    from datetime import timezone as _tz
    from sqlalchemy import text as sa_text

    for msg in messages:
        avito_message_id = str(msg.get("id") or "")
        if not avito_message_id:
            continue

        # Определяем тип и контент
        raw_type: str = msg.get("type", "text") or "text"
        content_block: dict = msg.get("content") or {}
        if raw_type == "text":
            content_text = content_block.get("text") or msg.get("text") or ""
            message_type = "text"
        elif raw_type == "image":
            sizes = content_block.get("image", {}).get("sizes", {})
            content_text = sizes.get("1280x960") or sizes.get("640x480") or ""
            message_type = "image"
        else:
            content_text = content_block.get("text") or ""
            message_type = "text"

        # Автор
        author_id = msg.get("author_id")
        if author_id and account.avito_user_id and int(author_id) == account.avito_user_id:
            author_type = "account"
        else:
            author_type = "candidate"

        # Timestamp
        created_raw = msg.get("created")
        if isinstance(created_raw, int):
            from datetime import datetime
            created_at = datetime.fromtimestamp(created_raw, tz=_tz.utc)
        else:
            created_at = None

        result = await db.execute(
            sa_text("""
                INSERT INTO chat_messages (
                    org_id, candidate_id, chat_id, avito_message_id,
                    content, message_type, author_type, created_at
                )
                SELECT
                    CAST(:org_id AS UUID), CAST(:candidate_id AS UUID), :chat_id,
                    :avito_message_id, :content, :message_type, :author_type,
                    COALESCE(CAST(:created_at AS TIMESTAMPTZ), now())
                WHERE NOT EXISTS (
                    SELECT 1 FROM chat_messages
                    WHERE avito_message_id = :avito_message_id
                      AND avito_message_id IS NOT NULL
                )
            """),
            {
                "org_id": str(org_id),
                "candidate_id": str(candidate_id),
                "chat_id": meta.chat_id,
                "avito_message_id": avito_message_id,
                "content": content_text,
                "message_type": message_type,
                "author_type": author_type,
                "created_at": created_at,
            },
        )
        added += result.rowcount

    await db.commit()
    return {"added": added}


# ===========================================================================
# Mark read
# ===========================================================================


@router.post(
    "/chat/{candidate_id}/read",
    status_code=status.HTTP_200_OK,
    summary="Отметить чат прочитанным",
    description="Сбрасывает unread_count через write-behind Redis.",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def mark_chat_read(
    candidate_id: uuid.UUID,
    request: Request,
    service: Annotated[ChatService, Depends(_get_chat_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.mark_read(request, candidate_id)


# ===========================================================================
# Legacy aliases (сохраняем обратную совместимость)
# ===========================================================================


@router.get(
    "/chats",
    response_model=ChatListResponse,
    summary="Список чатов (legacy)",
    include_in_schema=False,
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def legacy_chat_list(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(default=None, max_length=255),
    has_unread: bool | None = Query(default=None),
    avito_account_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
) -> ChatListResponse:
    # Переиспользуем логику из chat_list
    return await chat_list(
        request=request,
        db=db,
        redis=redis,
        _current_user=_current_user,
        search=search,
        has_unread=has_unread,
        avito_account_id=avito_account_id,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/chats/{candidate_id}",
    response_model=ChatMessagesResponse,
    summary="История сообщений (legacy)",
    include_in_schema=False,
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def legacy_get_messages(
    candidate_id: uuid.UUID,
    request: Request,
    service: Annotated[ChatService, Depends(_get_chat_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=50, ge=1, le=200),
    before: str | None = Query(default=None, description="Cursor — ISO datetime"),
) -> ChatMessagesResponse:
    return await service.get_messages(request, candidate_id, limit, before)


@router.post(
    "/chats/{candidate_id}/read",
    status_code=status.HTTP_200_OK,
    summary="Отметить чат прочитанным (legacy)",
    include_in_schema=False,
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def legacy_mark_read(
    candidate_id: uuid.UUID,
    request: Request,
    service: Annotated[ChatService, Depends(_get_chat_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.mark_read(request, candidate_id)


@router.get(
    "/filters",
    response_model=FilterOptionsResponse,
    summary="Значения для фильтров",
    description="Кешируется 5 минут. Возвращает этапы, теги, отделы, ответственных и аккаунты.",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_filter_options(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> FilterOptionsResponse:
    org_id = request.state.org_id
    cache = CacheService(redis)

    cached = await cache.get_org_filters(org_id)
    if cached:
        return FilterOptionsResponse(**cached)

    from app.models.avito import AvitoAccount
    from app.models.auth import User as UserModel
    from app.models.crm import PipelineStage, Tag
    from app.models.rbac import Department

    async def _fetch(stmt):  # type: ignore[no-untyped-def]
        result = await db.execute(stmt)
        return result.all()

    stages_rows = await _fetch(
        select(PipelineStage.id, PipelineStage.name, PipelineStage.color, PipelineStage.sort_order)
        .where(PipelineStage.org_id == org_id)
        .order_by(PipelineStage.sort_order)
    )
    tags_rows = await _fetch(
        select(Tag.id, Tag.name, Tag.color)
        .where(Tag.org_id == org_id)
        .order_by(Tag.name)
    )
    dept_rows = await _fetch(
        select(Department.id, Department.name)
        .where(Department.org_id == org_id)
        .order_by(Department.name)
    )
    user_rows = await _fetch(
        select(UserModel.id, UserModel.full_name)
        .where(UserModel.org_id == org_id, UserModel.is_active.is_(True))
        .order_by(UserModel.full_name)
    )
    account_rows = await _fetch(
        select(AvitoAccount.id, AvitoAccount.account_name)
        .where(AvitoAccount.org_id == org_id)
        .order_by(AvitoAccount.account_name)
    )

    data = FilterOptionsResponse(
        stages=[
            {"id": str(r.id), "name": r.name, "color": r.color, "sort_order": r.sort_order}
            for r in stages_rows
        ],
        tags=[{"id": str(r.id), "name": r.name, "color": r.color} for r in tags_rows],
        departments=[{"id": str(r.id), "name": r.name} for r in dept_rows],
        responsible_users=[{"id": str(r.id), "full_name": r.full_name} for r in user_rows],
        avito_accounts=[{"id": str(r.id), "name": r.account_name} for r in account_rows],
    )

    await cache.set_org_filters(org_id, data.model_dump(mode="json"))
    return data
