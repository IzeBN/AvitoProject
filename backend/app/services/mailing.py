"""
MailingService — создание заданий рассылки, управление статусами.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from app.models.mailing import MailingJob, MailingRecipient
from app.repositories.mailing import MailingRepository

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class MailingService:
    def __init__(self, repo: MailingRepository, redis: "Redis") -> None:
        self._repo = repo
        self._redis = redis

    async def create_by_ids(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        candidate_ids: list[uuid.UUID],
        message: str,
        file_url: str | None,
        scheduled_at: datetime | None,
        rate_limit_ms: int,
    ) -> MailingJob:
        job = MailingJob(
            org_id=org_id,
            created_by=user_id,
            message=message,
            file_url=file_url,
            criteria={"mode": "by_ids", "candidate_ids": [str(i) for i in candidate_ids]},
            scheduled_at=scheduled_at,
            rate_limit_ms=rate_limit_ms,
            total=len(candidate_ids),
            status="pending" if scheduled_at else "pending",
        )
        job = await self._repo.create(job)

        recipients = [
            MailingRecipient(
                mailing_job_id=job.id,
                candidate_id=cid,
                org_id=org_id,
                status="pending",
            )
            for cid in candidate_ids
        ]
        await self._repo.create_recipients_bulk(recipients)

        return job

    async def create_by_filters(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        filters: dict,
        candidate_ids: list[uuid.UUID],
        message: str,
        file_url: str | None,
        scheduled_at: datetime | None,
        rate_limit_ms: int,
    ) -> MailingJob:
        """candidate_ids должны быть уже разрезолвены по фильтрам в роутере."""
        job = MailingJob(
            org_id=org_id,
            created_by=user_id,
            message=message,
            file_url=file_url,
            criteria={"mode": "by_filters", "filters": filters},
            scheduled_at=scheduled_at,
            rate_limit_ms=rate_limit_ms,
            total=len(candidate_ids),
            status="pending",
        )
        job = await self._repo.create(job)

        recipients = [
            MailingRecipient(
                mailing_job_id=job.id,
                candidate_id=cid,
                org_id=org_id,
                status="pending",
            )
            for cid in candidate_ids
        ]
        await self._repo.create_recipients_bulk(recipients)

        return job

    async def create_by_phones(
        self,
        db: "AsyncSession",
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        phones: list[str],
        message: str,
        scheduled_at: datetime | None,
        rate_limit_ms: int,
        search_hash_key: bytes,
    ) -> MailingJob:
        """
        Создать рассылку по списку телефонов.
        Находит существующих кандидатов по phone_search_hash,
        для остальных создаёт минимальные записи кандидатов.
        """
        from sqlalchemy import select

        from app.models.crm import Candidate
        from app.security.encryption import compute_search_hash

        candidate_ids: list[uuid.UUID] = []
        for raw_phone in phones:
            phone = raw_phone.strip()
            if not phone:
                continue
            ph_hash = compute_search_hash(phone, search_hash_key)
            result = await db.execute(
                select(Candidate.id).where(
                    Candidate.org_id == org_id,
                    Candidate.phone_search_hash == ph_hash,
                    Candidate.deleted_at.is_(None),
                )
            )
            existing_id = result.scalar_one_or_none()
            if existing_id:
                candidate_ids.append(existing_id)
            else:
                from app.security.encryption import encrypt

                from app.config import get_settings
                settings = get_settings()
                enc_phone = encrypt(phone, settings.encryption_key_bytes)
                new_cand = Candidate(
                    org_id=org_id,
                    full_name=phone,
                    phone_enc=enc_phone,
                    phone_search_hash=ph_hash,
                    source="mailing_csv",
                )
                db.add(new_cand)
                await db.flush()
                candidate_ids.append(new_cand.id)

        job = MailingJob(
            org_id=org_id,
            created_by=user_id,
            message=message,
            file_url=None,
            criteria={"mode": "by_phones", "phones": phones},
            scheduled_at=scheduled_at,
            rate_limit_ms=rate_limit_ms,
            total=len(candidate_ids),
            status="pending",
        )
        job = await self._repo.create(job)

        recipients = [
            MailingRecipient(
                mailing_job_id=job.id,
                candidate_id=cid,
                org_id=org_id,
                status="pending",
            )
            for cid in candidate_ids
        ]
        if recipients:
            await self._repo.create_recipients_bulk(recipients)

        return job

    async def get_with_progress(
        self, org_id: uuid.UUID, job_id: uuid.UUID
    ) -> MailingJob | None:
        return await self._repo.get_by_id(org_id, job_id)

    async def get_progress_from_redis(self, job_id: uuid.UUID) -> dict:
        """Получить прогресс рассылки из Redis (обновляется воркером каждые 10 отправок)."""
        raw = await self._redis.hgetall(f"mailing:{job_id}:progress")
        if not raw:
            return {}
        decoded = {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in raw.items()
        }
        sent = int(decoded.get("sent", 0))
        failed = int(decoded.get("failed", 0))
        total = int(decoded.get("total", 0))
        percent = round((sent + failed) / total * 100, 1) if total > 0 else 0.0
        return {"sent": sent, "failed": failed, "total": total, "percent": percent}

    async def pause(self, org_id: uuid.UUID, job_id: uuid.UUID) -> None:
        job = await self._require_job(org_id, job_id)
        if job.status != "running":
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Рассылку можно поставить на паузу только в статусе running",
            )
        await self._redis.setex(f"mailing:{job_id}:pause", 3600, "1")
        await self._repo.update_status(
            job_id, "paused", paused_at=datetime.utcnow()
        )

    async def resume(self, org_id: uuid.UUID, job_id: uuid.UUID) -> MailingJob:
        job = await self._require_job(org_id, job_id)
        if job.status != "paused":
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Рассылку можно возобновить только в статусе paused",
            )
        await self._redis.delete(f"mailing:{job_id}:pause")
        await self._repo.update_status(
            job_id, "resuming", resumed_at=datetime.utcnow()
        )
        return job

    async def cancel(self, org_id: uuid.UUID, job_id: uuid.UUID) -> None:
        job = await self._require_job(org_id, job_id)
        if job.status in ("done", "cancelled", "failed"):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Нельзя отменить рассылку в статусе {job.status}",
            )
        await self._redis.setex(f"mailing:{job_id}:stop", 3600, "1")
        await self._repo.skip_all_pending(job_id)
        await self._repo.update_status(job_id, "cancelled")

    async def _require_job(
        self, org_id: uuid.UUID, job_id: uuid.UUID
    ) -> MailingJob:
        job = await self._repo.get_by_id(org_id, job_id)
        if job is None:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рассылка не найдена")
        return job
