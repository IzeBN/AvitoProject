"""
MailingRepository — доступ к данным рассылок и получателей.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mailing import MailingJob, MailingRecipient


class MailingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # MailingJob
    # ------------------------------------------------------------------

    async def get_all(
        self,
        org_id: uuid.UUID,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[MailingJob]:
        conditions = [MailingJob.org_id == org_id]
        if status_filter:
            conditions.append(MailingJob.status == status_filter)
        result = await self._db.execute(
            select(MailingJob)
            .where(*conditions)
            .order_by(MailingJob.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, org_id: uuid.UUID, job_id: uuid.UUID
    ) -> MailingJob | None:
        result = await self._db.execute(
            select(MailingJob).where(
                MailingJob.org_id == org_id,
                MailingJob.id == job_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_any_org(self, job_id: uuid.UUID) -> MailingJob | None:
        result = await self._db.execute(
            select(MailingJob).where(MailingJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def create(self, job: MailingJob) -> MailingJob:
        self._db.add(job)
        await self._db.flush()
        await self._db.refresh(job)
        return job

    async def update_status(
        self,
        job_id: uuid.UUID,
        status: str,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        paused_at: datetime | None = None,
        resumed_at: datetime | None = None,
        arq_job_id: str | None = None,
        last_error: str | None = None,
    ) -> None:
        values: dict = {"status": status}
        if started_at is not None:
            values["started_at"] = started_at
        if finished_at is not None:
            values["finished_at"] = finished_at
        if paused_at is not None:
            values["paused_at"] = paused_at
        if resumed_at is not None:
            values["resumed_at"] = resumed_at
        if arq_job_id is not None:
            values["arq_job_id"] = arq_job_id
        if last_error is not None:
            values["last_error"] = last_error

        await self._db.execute(
            update(MailingJob).where(MailingJob.id == job_id).values(**values)
        )

    async def update_counters(
        self,
        job_id: uuid.UUID,
        sent: int,
        failed: int,
        skipped: int,
    ) -> None:
        await self._db.execute(
            update(MailingJob)
            .where(MailingJob.id == job_id)
            .values(sent=sent, failed=failed, skipped=skipped)
        )

    async def get_scheduled_pending(self) -> list[MailingJob]:
        """Получить рассылки у которых scheduled_at <= now() и status='pending'."""
        from sqlalchemy import func

        result = await self._db.execute(
            select(MailingJob).where(
                MailingJob.status == "pending",
                MailingJob.scheduled_at.is_not(None),
                MailingJob.scheduled_at <= func.now(),
            )
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # MailingRecipient
    # ------------------------------------------------------------------

    async def create_recipients_bulk(
        self, recipients: list[MailingRecipient]
    ) -> None:
        self._db.add_all(recipients)
        await self._db.flush()

    async def get_pending_recipients(
        self,
        job_id: uuid.UUID,
        after_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[MailingRecipient]:
        """
        Cursor-based чтение pending получателей.
        after_id — последний обработанный id (для возобновления после паузы).
        """
        q = select(MailingRecipient).where(
            MailingRecipient.mailing_job_id == job_id,
            MailingRecipient.status == "pending",
        )
        if after_id is not None:
            q = q.where(MailingRecipient.id > after_id)
        q = q.order_by(MailingRecipient.id).limit(limit)
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def get_recipients_page(
        self,
        job_id: uuid.UUID,
        offset: int,
        limit: int,
    ) -> tuple[list[MailingRecipient], int]:
        from sqlalchemy import func

        count_result = await self._db.execute(
            select(func.count()).where(
                MailingRecipient.mailing_job_id == job_id
            )
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(MailingRecipient)
            .where(MailingRecipient.mailing_job_id == job_id)
            .order_by(MailingRecipient.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update_recipient(
        self,
        recipient_id: uuid.UUID,
        status: str,
        attempt_count: int,
        sent_at: datetime | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        from sqlalchemy import func

        values: dict = {
            "status": status,
            "attempt_count": attempt_count,
            "last_attempt_at": func.now(),
        }
        if sent_at is not None:
            values["sent_at"] = sent_at
        if error_code is not None:
            values["error_code"] = error_code
        if error_message is not None:
            values["error_message"] = error_message

        await self._db.execute(
            update(MailingRecipient)
            .where(MailingRecipient.id == recipient_id)
            .values(**values)
        )

    async def skip_all_pending(self, job_id: uuid.UUID) -> None:
        """Перевести всех pending получателей в skipped (при отмене)."""
        await self._db.execute(
            update(MailingRecipient)
            .where(
                MailingRecipient.mailing_job_id == job_id,
                MailingRecipient.status == "pending",
            )
            .values(status="skipped")
        )

    async def count_by_status(self, job_id: uuid.UUID) -> dict[str, int]:
        from sqlalchemy import func

        result = await self._db.execute(
            select(MailingRecipient.status, func.count())
            .where(MailingRecipient.mailing_job_id == job_id)
            .group_by(MailingRecipient.status)
        )
        return {row[0]: row[1] for row in result.all()}
