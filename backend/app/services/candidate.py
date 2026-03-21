"""
CandidateService — бизнес-логика работы с кандидатами.
"""

import hashlib
import logging
import uuid
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.candidate import CandidateRepository
from app.schemas.candidate import (
    BulkEditByFiltersRequest,
    BulkEditRequest,
    BulkEditResponse,
    CandidateCreate,
    CandidateEdit,
    CandidateFilters,
    CandidateListResponse,
    CandidateResponse,
    DepartmentShort,
    StageShort,
    TagShort,
    UserShort,
)
from app.services.audit import AuditService
from app.services.cache import CacheService

logger = logging.getLogger(__name__)


def _has_permission(request: Request, permission: str) -> bool:
    """Проверить право в request.state (список granted прав)."""
    granted: list = getattr(request.state, "permissions_granted", [])
    role: str = getattr(request.state, "user_role", "")
    return role == "superadmin" or permission in granted


def _candidate_to_response(
    candidate: Any,
    chat_meta: dict | None = None,
    phone: str | None = None,
    tags_map: dict | None = None,  # candidate_id -> list[TagShort]
) -> CandidateResponse:
    """Преобразовать ORM-объект Candidate в CandidateResponse."""
    # Теги — из предзагруженного словаря
    tags: list[TagShort] = []
    if tags_map is not None:
        tags = tags_map.get(candidate.id, [])

    # Этап
    stage = None
    if candidate.stage_id and hasattr(candidate, "stage") and candidate.stage:
        s = candidate.stage
        stage = StageShort(
            id=s.id, name=s.name, color=s.color, sort_order=s.sort_order
        )

    # Отдел
    department = None
    if candidate.department_id and hasattr(candidate, "department") and candidate.department:
        d = candidate.department
        department = DepartmentShort(id=d.id, name=d.name)

    # Ответственный
    responsible = None
    if candidate.responsible_id and hasattr(candidate, "responsible") and candidate.responsible:
        r = candidate.responsible
        responsible = UserShort(id=r.id, full_name=r.full_name, email=r.email)

    last_message = None
    last_message_at = None
    unread_count = 0

    if chat_meta:
        last_message = chat_meta.get("last_message")
        last_message_at = chat_meta.get("last_message_at")
        unread_count = int(chat_meta.get("unread_count", 0))

    return CandidateResponse(
        id=candidate.id,
        name=candidate.name,
        phone=phone,
        vacancy=candidate.vacancy,
        location=candidate.location,
        stage=stage,
        department=department,
        responsible=responsible,
        tags=tags,
        comment=candidate.comment,
        due_date=candidate.due_date,
        has_new_message=candidate.has_new_message,
        last_message=last_message,
        last_message_at=last_message_at,
        unread_count=unread_count,
        source=candidate.source,
        avito_account_id=candidate.avito_account_id,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


class CandidateService:
    """
    Сервис кандидатов CRM.

    Координирует репозиторий, кеш, аудит и шифрование.
    """

    def __init__(
        self,
        repo: CandidateRepository,
        cache: CacheService,
        audit: AuditService,
        encryption_key: bytes,
        search_hash_key: bytes,
        db: AsyncSession,
    ) -> None:
        self._repo = repo
        self._cache = cache
        self._audit = audit
        self._enc_key = encryption_key
        self._hash_key = search_hash_key
        self._db = db

    def _compute_filters_hash(self, filters: CandidateFilters, page: int) -> str:
        """MD5 от JSON-сериализации фильтров + страница."""
        raw = filters.model_dump_json() + f":{page}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _decrypt_phone(self, phone_enc: str | None) -> str | None:
        """Расшифровать телефон кандидата."""
        if not phone_enc:
            return None
        try:
            from app.security.encryption import decrypt
            return decrypt(phone_enc, self._enc_key)
        except Exception:
            logger.warning("Failed to decrypt phone")
            return None

    def _search_hash(self, value: str) -> str:
        from app.security.encryption import compute_search_hash
        return compute_search_hash(value, self._hash_key)

    async def get_list(
        self,
        request: Request,
        filters: CandidateFilters,
        page: int,
        page_size: int,
    ) -> CandidateListResponse:
        """
        Получить список кандидатов.

        1. Попытка читать из Redis кеша
        2. Если нет — загрузить из БД
        3. Расшифровать phone при наличии права
        4. Положить в кеш
        """
        org_id: uuid.UUID = request.state.org_id
        can_view_phone = _has_permission(request, "crm.candidates.view_phone")
        user_departments: list[uuid.UUID] | None = getattr(
            request.state, "user_departments", None
        )

        filters_hash = self._compute_filters_hash(filters, page)

        # Кеш только для случаев без расшифровки телефона (иначе leak across users)
        if not can_view_phone:
            cached = await self._cache.get_candidates_list(org_id, filters_hash, page)
            if cached is not None:
                return CandidateListResponse.model_validate(cached)

        # Загружаем из БД
        candidates, total = await self._repo.get_list(
            org_id=org_id,
            filters=filters,
            page=page,
            page_size=page_size,
            user_departments=user_departments,
            search_hash_fn=self._search_hash,
        )

        # Загружаем метаданные чатов батчем
        chat_ids = [c.chat_id for c in candidates if c.chat_id]
        chat_metas: dict[str, dict] = {}
        if chat_ids:
            chat_metas = await self._load_chat_metas(chat_ids, org_id)

        # Формируем ответы
        # Загружаем теги батчем для всех кандидатов
        candidate_ids = [c.id for c in candidates]
        tags_map = await self._load_tags(candidate_ids) if candidate_ids else {}

        items = []
        for c in candidates:
            meta = chat_metas.get(c.chat_id) if c.chat_id else None
            phone = self._decrypt_phone(c.phone_enc) if can_view_phone else None
            items.append(_candidate_to_response(c, meta, phone, tags_map))

        response = CandidateListResponse.create(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

        # Кешируем только если не показываем телефон
        if not can_view_phone:
            cache_data = response.model_dump(mode="json")
            await self._cache.set_candidates_list(org_id, filters_hash, page, cache_data)

        return response

    async def _load_tags(
        self, candidate_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[TagShort]]:
        """Загрузить теги кандидатов батчем."""
        from sqlalchemy import select
        from app.models.crm import CandidateTag, Tag

        result = await self._db.execute(
            select(CandidateTag.candidate_id, Tag.id, Tag.name, Tag.color)
            .join(Tag, Tag.id == CandidateTag.tag_id)
            .where(CandidateTag.candidate_id.in_(candidate_ids))
        )
        rows = result.all()
        tags_map: dict[uuid.UUID, list[TagShort]] = {}
        for row in rows:
            cid = row[0]
            tag = TagShort(id=row[1], name=row[2], color=row[3])
            tags_map.setdefault(cid, []).append(tag)
        return tags_map

    async def _load_chat_metas(
        self, chat_ids: list[str], org_id: uuid.UUID
    ) -> dict[str, dict]:
        """Загрузить метаданные чатов из БД батчем."""
        from sqlalchemy import select, and_
        from app.models.chat import ChatMetadata

        result = await self._db.execute(
            select(ChatMetadata).where(
                ChatMetadata.chat_id.in_(chat_ids),
                ChatMetadata.org_id == org_id,
            )
        )
        metas = result.scalars().all()
        return {
            m.chat_id: {
                "last_message": m.last_message,
                "last_message_at": m.last_message_at,
                "unread_count": m.unread_count,
            }
            for m in metas
        }

    async def get_one(
        self, request: Request, candidate_id: uuid.UUID
    ) -> CandidateResponse:
        """Получить одного кандидата по ID."""
        org_id: uuid.UUID = request.state.org_id
        can_view_phone = _has_permission(request, "crm.candidates.view_phone")

        candidate = await self._repo.get_by_id_with_relations(org_id, candidate_id)
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Кандидат не найден",
            )

        meta = None
        if candidate.chat_id:
            metas = await self._load_chat_metas([candidate.chat_id], org_id)
            meta = metas.get(candidate.chat_id)

        tags_map = await self._load_tags([candidate.id])
        phone = self._decrypt_phone(candidate.phone_enc) if can_view_phone else None
        return _candidate_to_response(candidate, meta, phone, tags_map)

    async def update(
        self,
        request: Request,
        candidate_id: uuid.UUID,
        data: CandidateEdit,
    ) -> CandidateResponse:
        """Обновить кандидата и инвалидировать кеш."""
        org_id: uuid.UUID = request.state.org_id

        candidate = await self._repo.get_by_id_with_relations(org_id, candidate_id)
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Кандидат не найден",
            )

        # Определяем что именно изменилось для аудита
        update_dict = data.model_dump(exclude_none=True)
        if not update_dict:
            return await self.get_one(request, candidate_id)

        old_stage_id = candidate.stage_id

        # Применяем обновление
        await self._repo.update(candidate, **update_dict)
        await self._db.commit()
        await self._db.refresh(candidate)

        # Инвалидируем кеш
        await self._cache.invalidate_candidates(org_id)

        # Определяем тип аудит-события
        action = "candidate.update"
        if "stage_id" in update_dict and update_dict["stage_id"] != old_stage_id:
            action = "candidate.stage_changed"

        await self._audit.log(
            action=action,
            entity_type="candidate",
            entity_id=candidate_id,
            entity_display=candidate.name or str(candidate_id),
            details=update_dict,
            human_readable=(
                f"Обновлён кандидат {candidate.name or candidate_id}: "
                + ", ".join(f"{k}={v}" for k, v in update_dict.items())
            ),
        )

        return await self.get_one(request, candidate_id)

    async def bulk_update(
        self, request: Request, data: BulkEditRequest
    ) -> BulkEditResponse:
        """Массовое обновление по списку ID."""
        org_id: uuid.UUID = request.state.org_id
        update_dict = data.edit.model_dump(exclude_none=True)

        if not update_dict:
            return BulkEditResponse(updated=0, message="Нет данных для обновления")

        updated = await self._repo.bulk_update(
            org_id=org_id,
            candidate_ids=data.candidate_ids,
            data=update_dict,
        )
        await self._db.commit()
        await self._cache.invalidate_candidates(org_id)

        await self._audit.log(
            action="candidate.bulk_update",
            entity_type="candidate",
            details={
                "count": updated,
                "candidate_ids": [str(i) for i in data.candidate_ids],
                **update_dict,
            },
            human_readable=f"Массовое обновление {updated} кандидатов",
        )

        return BulkEditResponse(
            updated=updated,
            message=f"Обновлено {updated} кандидатов",
        )

    async def bulk_update_by_filters(
        self, request: Request, data: BulkEditByFiltersRequest
    ) -> BulkEditResponse:
        """Массовое обновление по фильтрам."""
        org_id: uuid.UUID = request.state.org_id
        user_departments: list[uuid.UUID] | None = getattr(
            request.state, "user_departments", None
        )
        update_dict = data.edit.model_dump(exclude_none=True)

        if not update_dict:
            return BulkEditResponse(updated=0, message="Нет данных для обновления")

        updated = await self._repo.bulk_update_by_filters(
            org_id=org_id,
            filters=data.filters,
            data=update_dict,
            user_departments=user_departments,
        )
        await self._db.commit()
        await self._cache.invalidate_candidates(org_id)

        await self._audit.log(
            action="candidate.bulk_update_by_filters",
            entity_type="candidate",
            details={"count": updated, **update_dict},
            human_readable=f"Массовое обновление по фильтрам: {updated} кандидатов",
        )

        return BulkEditResponse(
            updated=updated,
            message=f"Обновлено {updated} кандидатов",
        )

    async def create(
        self,
        request: Request,
        data: CandidateCreate,
    ) -> CandidateResponse:
        """
        Создать нового кандидата.

        1. Шифрует телефон, вычисляет HMAC хеш для поиска
        2. Создаёт запись в БД
        3. Привязывает теги если переданы
        4. Инвалидирует кеш
        5. Пишет аудит
        """
        org_id: uuid.UUID = request.state.org_id

        phone_enc = None
        phone_search_hash = None
        if data.phone:
            from app.security.encryption import encrypt
            phone_enc = encrypt(data.phone, self._enc_key)
            phone_search_hash = self._search_hash(data.phone)

        candidate = await self._repo.create_candidate(
            org_id=org_id,
            name=data.full_name,
            phone_enc=phone_enc,
            phone_search_hash=phone_search_hash,
            stage_id=data.stage_id,
            department_id=data.department_id,
            responsible_id=data.assigned_to,
            avito_account_id=data.avito_account_id,
            source=data.source,
            comment=data.notes,
        )

        # Привязываем теги
        if data.tag_ids:
            for tag_id in data.tag_ids:
                try:
                    await self._repo.add_tag(org_id, candidate.id, tag_id)
                except Exception:
                    logger.warning("Could not attach tag %s to candidate %s", tag_id, candidate.id)

        await self._db.commit()
        await self._db.refresh(candidate)
        await self._cache.invalidate_candidates(org_id)

        await self._audit.log(
            action="candidate.create",
            entity_type="candidate",
            entity_id=candidate.id,
            entity_display=candidate.name or str(candidate.id),
            details={
                "stage_id": str(data.stage_id) if data.stage_id else None,
                "source": data.source,
            },
            human_readable=f"Создан кандидат: {candidate.name or candidate.id}",
        )

        return await self.get_one(request, candidate.id)

    async def soft_delete(
        self, request: Request, candidate_id: uuid.UUID
    ) -> None:
        """Мягко удалить кандидата."""
        org_id: uuid.UUID = request.state.org_id

        candidate = await self._repo.soft_delete(org_id, candidate_id)
        if candidate is None:
            from fastapi import HTTPException, status as http_status
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Кандидат не найден",
            )

        await self._db.commit()
        await self._cache.invalidate_candidates(org_id)

        await self._audit.log(
            action="candidate.delete",
            entity_type="candidate",
            entity_id=candidate_id,
            entity_display=candidate.name or str(candidate_id),
            details={},
            human_readable=f"Удалён кандидат: {candidate.name or candidate_id}",
        )

    async def add_tag(
        self, request: Request, candidate_id: uuid.UUID, tag_id: uuid.UUID
    ) -> None:
        """Добавить тег кандидату."""
        org_id: uuid.UUID = request.state.org_id
        await self._repo.add_tag(org_id, candidate_id, tag_id)
        await self._db.commit()
        await self._cache.invalidate_candidates(org_id)

        await self._audit.log(
            action="candidate.tag_added",
            entity_type="candidate",
            entity_id=candidate_id,
            details={"tag_id": str(tag_id)},
            human_readable=f"Добавлен тег {tag_id} кандидату {candidate_id}",
        )

    async def remove_tag(
        self, request: Request, candidate_id: uuid.UUID, tag_id: uuid.UUID
    ) -> None:
        """Удалить тег с кандидата."""
        org_id: uuid.UUID = request.state.org_id
        await self._repo.remove_tag(org_id, candidate_id, tag_id)
        await self._db.commit()
        await self._cache.invalidate_candidates(org_id)

        await self._audit.log(
            action="candidate.tag_removed",
            entity_type="candidate",
            entity_id=candidate_id,
            details={"tag_id": str(tag_id)},
            human_readable=f"Удалён тег {tag_id} с кандидата {candidate_id}",
        )
