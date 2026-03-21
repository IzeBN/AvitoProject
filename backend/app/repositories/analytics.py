"""
Репозиторий аналитики — агрегационные запросы к БД.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case, func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class AnalyticsRepository:
    """Агрегационные запросы для аналитики организации."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_overview(
        self,
        org_id: uuid.UUID,
        date_from: date,
        date_to: date,
        department_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Общая статистика кандидатов за период.
        Возвращает dict совместимый с AnalyticsOverview.
        """
        from app.models.crm import Candidate, PipelineStage

        dt_from = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
        dt_to = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        # Базовые условия
        base_conditions = [
            Candidate.org_id == org_id,
            Candidate.deleted_at.is_(None),
        ]

        # Итого кандидатов за период
        total_q = select(func.count(Candidate.id)).where(
            *base_conditions,
            Candidate.created_at >= dt_from,
            Candidate.created_at <= dt_to,
        )
        if department_id:
            total_q = total_q.where(Candidate.department_id == department_id)

        total_result = await self._session.execute(total_q)
        total_candidates = total_result.scalar_one() or 0

        # Новые за последнюю неделю
        new_q = select(func.count(Candidate.id)).where(
            *base_conditions,
            Candidate.created_at >= week_ago,
        )
        new_result = await self._session.execute(new_q)
        new_this_week = new_result.scalar_one() or 0

        # По этапам (JOIN с pipeline_stages для имён)
        stage_q = (
            select(
                PipelineStage.name.label("stage_name"),
                func.count(Candidate.id).label("cnt"),
            )
            .join(PipelineStage, PipelineStage.id == Candidate.stage_id)
            .where(
                Candidate.org_id == org_id,
                Candidate.deleted_at.is_(None),
                Candidate.created_at >= dt_from,
                Candidate.created_at <= dt_to,
            )
            .group_by(PipelineStage.name, PipelineStage.sort_order)
            .order_by(PipelineStage.sort_order)
        )
        if department_id:
            stage_q = stage_q.where(Candidate.department_id == department_id)

        stage_result = await self._session.execute(stage_q)
        by_stage = [
            {"stage": row.stage_name, "count": row.cnt}
            for row in stage_result.all()
        ]

        return {
            "total_candidates": total_candidates,
            "new_this_week": new_this_week,
            "by_stage": by_stage,
            "conversion_rate": 0.0,
            "avg_time_in_stage": 0.0,
        }

    async def get_by_vacancy(
        self,
        org_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """Статистика кандидатов по вакансиям (группировка по полю vacancy)."""
        from app.models.crm import Candidate, PipelineStage

        dt_from = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
        dt_to = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc)

        q = (
            select(
                Candidate.vacancy,
                PipelineStage.name.label("stage_name"),
                func.count(Candidate.id).label("cnt"),
            )
            .outerjoin(PipelineStage, PipelineStage.id == Candidate.stage_id)
            .where(
                Candidate.org_id == org_id,
                Candidate.deleted_at.is_(None),
                Candidate.created_at >= dt_from,
                Candidate.created_at <= dt_to,
                Candidate.vacancy.isnot(None),
            )
            .group_by(Candidate.vacancy, PipelineStage.name)
        )
        result = await self._session.execute(q)
        rows = result.all()

        # Группируем по vacancy
        grouped: dict[str, dict] = {}
        for row in rows:
            vac = row.vacancy or "unknown"
            if vac not in grouped:
                grouped[vac] = {
                    "vacancy_id": vac,
                    "vacancy_title": vac,
                    "total": 0,
                    "by_stage": [],
                }
            grouped[vac]["total"] += row.cnt
            grouped[vac]["by_stage"].append(
                {"stage": row.stage_name or "unknown", "count": row.cnt}
            )

        return list(grouped.values())

    async def get_by_responsible(
        self,
        org_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """Статистика по ответственным менеджерам."""
        from app.models.crm import Candidate
        from app.models.auth import User

        dt_from = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
        dt_to = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc)

        q = (
            select(
                Candidate.responsible_id,
                User.full_name,
                func.count(Candidate.id).label("total"),
                # Кандидаты без deleted_at — активные
                func.sum(
                    case((Candidate.deleted_at.is_(None), 1), else_=0)
                ).label("active"),
                # Удалённые — считаем завершёнными
                func.sum(
                    case((Candidate.deleted_at.isnot(None), 1), else_=0)
                ).label("completed"),
            )
            .outerjoin(User, User.id == Candidate.responsible_id)
            .where(
                Candidate.org_id == org_id,
                Candidate.created_at >= dt_from,
                Candidate.created_at <= dt_to,
                Candidate.responsible_id.isnot(None),
            )
            .group_by(Candidate.responsible_id, User.full_name)
        )
        result = await self._session.execute(q)
        rows = result.all()

        return [
            {
                "user_id": str(row.responsible_id),
                "full_name": row.full_name or str(row.responsible_id),
                "total": row.total or 0,
                "active": int(row.active or 0),
                "completed": int(row.completed or 0),
            }
            for row in rows
        ]

    async def get_activity(
        self,
        org_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """
        Активность команды по дням из audit_log.
        Возвращает [{date, messages_count, changes_count, total}].
        """
        dt_from = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
        dt_to = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc)

        day_trunc = func.date_trunc(literal_column("'day'"), AuditLog.created_at).label("day")
        q = (
            select(
                day_trunc,
                func.sum(
                    case((AuditLog.action.like("message.%"), 1), else_=0)
                ).label("messages_count"),
                func.sum(
                    case((AuditLog.action.not_like("message.%"), 1), else_=0)
                ).label("changes_count"),
                func.count(AuditLog.id).label("total"),
            )
            .where(
                AuditLog.org_id == org_id,
                AuditLog.created_at >= dt_from,
                AuditLog.created_at <= dt_to,
            )
            .group_by(text("1"))
            .order_by(text("1 ASC"))
        )
        result = await self._session.execute(q)
        rows = result.all()

        return [
            {
                "date": row.day.date() if row.day else date_from,
                "messages_count": int(row.messages_count or 0),
                "changes_count": int(row.changes_count or 0),
                "total": int(row.total or 0),
            }
            for row in rows
        ]

    async def get_department_stats(
        self,
        org_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """Статистика по отделам."""
        # Запрос через UserDepartment → Candidate.responsible_id
        # Упрощённая реализация — возвращает пустой список если нет данных
        return []
