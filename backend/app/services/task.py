"""
TaskService — бизнес-логика задач.
"""

import logging
import math
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.task import TaskRepository
from app.schemas.task import (
    AssigneeInfo,
    CandidateInfo,
    TaskCreate,
    TaskFilters,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


def _parse_due_date(due_date: str | None) -> date | None:
    """Распарсить строку 'YYYY-MM-DD' в объект date."""
    if due_date is None:
        return None
    try:
        return date.fromisoformat(due_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Некорректный формат due_date: '{due_date}'. Ожидается YYYY-MM-DD",
        ) from exc


def _format_due_date(deadline: datetime | None) -> str | None:
    """Форматировать datetime (deadline из БД) в строку 'YYYY-MM-DD'."""
    if deadline is None:
        return None
    return deadline.date().isoformat()


def _build_task_response(task) -> TaskResponse:  # noqa: ANN001
    """Собрать TaskResponse из ORM-объекта Task с загруженными relationship."""
    assignee: AssigneeInfo | None = None
    if task.assignee is not None:
        assignee = AssigneeInfo(
            id=task.assignee.id,
            full_name=task.assignee.full_name,
        )

    candidate: CandidateInfo | None = None
    if task.candidate_rel is not None:
        candidate = CandidateInfo(
            id=task.candidate_rel.id,
            name=task.candidate_rel.name,
        )

    return TaskResponse(
        id=task.id,
        org_id=task.org_id,
        title=task.title,
        description=task.description,
        due_date=_format_due_date(task.deadline),
        priority=task.priority,
        status=task.status,
        assignee=assignee,
        candidate=candidate,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


class TaskService:
    """Сервис управления задачами CRM."""

    def __init__(
        self,
        repo: TaskRepository,
        audit: AuditService,
        db: AsyncSession,
    ) -> None:
        self._repo = repo
        self._audit = audit
        self._db = db

    async def get_list(
        self,
        request: Request,
        filters: TaskFilters,
        page: int,
        page_size: int,
    ) -> TaskListResponse:
        org_id: uuid.UUID = request.state.org_id
        tasks, total = await self._repo.get_list(
            org_id=org_id, filters=filters, page=page, page_size=page_size
        )
        pages = max(1, math.ceil(total / page_size)) if page_size > 0 else 1
        items = [_build_task_response(t) for t in tasks]
        return TaskListResponse(
            items=items, total=total, page=page, page_size=page_size, pages=pages
        )

    async def create(self, request: Request, data: TaskCreate) -> TaskResponse:
        org_id: uuid.UUID = request.state.org_id
        user_id: uuid.UUID = request.state.user_id

        # Если responsible_id не передан — назначить на текущего пользователя
        responsible_id = data.responsible_id if data.responsible_id is not None else user_id

        deadline = _parse_due_date(data.due_date)

        task = await self._repo.create(
            org_id=org_id,
            responsible_id=responsible_id,
            created_by=user_id,
            candidate_id=data.candidate_id,
            title=data.title,
            description=data.description,
            deadline=deadline,
            priority=data.priority,
            status=data.status,
        )
        await self._db.commit()

        # Перезагрузить с relationship
        task = await self._repo.get_by_org(org_id, task.id)

        await self._audit.log(
            action="task.create",
            entity_type="task",
            entity_id=task.id,
            entity_display=task.title,
            details=data.model_dump(mode="json"),
            human_readable=f"Создана задача: {task.title}",
        )

        return _build_task_response(task)

    async def update(
        self, request: Request, task_id: uuid.UUID, data: TaskUpdate
    ) -> TaskResponse:
        org_id: uuid.UUID = request.state.org_id
        task = await self._repo.get_by_org(org_id, task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена"
            )

        update_dict = data.model_dump(exclude_none=True)

        # Перевести due_date → deadline
        if "due_date" in update_dict:
            update_dict["deadline"] = _parse_due_date(update_dict.pop("due_date"))

        # Синхронизировать is_completed / completed_at при смене статуса
        if "status" in update_dict:
            new_status = update_dict["status"]
            if new_status == "done":
                update_dict["is_completed"] = True
                update_dict["completed_at"] = datetime.now(timezone.utc)
            else:
                update_dict["is_completed"] = False
                update_dict["completed_at"] = None

        if update_dict:
            await self._repo.update(task, **update_dict)
            await self._db.commit()

            # Перезагрузить с relationship
            task = await self._repo.get_by_org(org_id, task_id)

            await self._audit.log(
                action="task.update",
                entity_type="task",
                entity_id=task_id,
                entity_display=task.title,
                details=data.model_dump(mode="json", exclude_none=True),
                human_readable=f"Обновлена задача: {task.title}",
            )

        return _build_task_response(task)

    async def delete(self, request: Request, task_id: uuid.UUID) -> None:
        org_id: uuid.UUID = request.state.org_id
        task = await self._repo.get_by_org(org_id, task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена"
            )

        title = task.title
        await self._repo.delete(task)
        await self._db.commit()

        await self._audit.log(
            action="task.delete",
            entity_type="task",
            entity_id=task_id,
            entity_display=title,
            details={},
            human_readable=f"Удалена задача: {title}",
        )

    async def complete(self, request: Request, task_id: uuid.UUID) -> TaskResponse:
        org_id: uuid.UUID = request.state.org_id
        task = await self._repo.get_by_org(org_id, task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена"
            )

        if task.is_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Задача уже выполнена",
            )

        task = await self._repo.complete(task)
        await self._db.commit()

        # Перезагрузить с relationship
        task = await self._repo.get_by_org(org_id, task_id)

        await self._audit.log(
            action="task.complete",
            entity_type="task",
            entity_id=task_id,
            entity_display=task.title,
            details={},
            human_readable=f"Задача выполнена: {task.title}",
        )

        return _build_task_response(task)
