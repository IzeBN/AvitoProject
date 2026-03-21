"""
Репозиторий задач.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.auth import User
from app.models.crm import Candidate
from app.models.task import Task
from app.repositories.base import BaseRepository
from app.schemas.task import TaskFilters


class TaskRepository(BaseRepository[Task]):
    model = Task

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_list(
        self,
        org_id: uuid.UUID,
        filters: TaskFilters,
        page: int,
        page_size: int,
    ) -> tuple[list[Task], int]:
        """Получить список задач с фильтрами и пагинацией."""
        conditions = [Task.org_id == org_id]

        if filters.responsible_id is not None:
            conditions.append(Task.responsible_id == filters.responsible_id)

        if filters.candidate_id is not None:
            conditions.append(Task.candidate_id == filters.candidate_id)

        if filters.status is not None:
            conditions.append(Task.status == filters.status)

        where_clause = and_(*conditions)

        count_stmt = select(func.count(Task.id)).where(where_clause)
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(Task)
            .where(where_clause)
            .options(
                joinedload(Task.assignee),
                joinedload(Task.candidate_rel),
            )
            .order_by(Task.deadline.asc().nullslast(), Task.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self._session.execute(stmt)
        items = list(result.scalars().unique().all())

        return items, total

    async def get_by_org(self, org_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
        result = await self._session.execute(
            select(Task)
            .where(Task.id == task_id, Task.org_id == org_id)
            .options(
                joinedload(Task.assignee),
                joinedload(Task.candidate_rel),
            )
        )
        return result.scalar_one_or_none()

    async def complete(self, task: Task) -> Task:
        """Отметить задачу выполненной."""
        task.is_completed = True
        task.completed_at = datetime.now(timezone.utc)
        task.status = "done"
        self._session.add(task)
        await self._session.flush()
        await self._session.refresh(task)
        return task
