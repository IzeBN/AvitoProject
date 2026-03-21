"""
Роутер задач.

GET    /api/v1/tasks                 — список задач
POST   /api/v1/tasks                 — создать
PATCH  /api/v1/tasks/{id}            — обновить
DELETE /api/v1/tasks/{id}            — удалить
POST   /api/v1/tasks/{id}/complete   — отметить выполненной
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.auth import User
from app.repositories.task import TaskRepository
from app.schemas.task import (
    TaskCreate,
    TaskFilters,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)
from app.services.audit import AuditService
from app.services.task import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_task_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> TaskService:
    return TaskService(
        repo=TaskRepository(db),
        audit=AuditService(db, request),
        db=db,
    )


@router.get(
    "",
    response_model=TaskListResponse,
    summary="Список задач",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def list_tasks(
    request: Request,
    service: Annotated[TaskService, Depends(_get_task_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    responsible_id: uuid.UUID | None = Query(default=None),
    candidate_id: uuid.UUID | None = Query(default=None),
    is_completed: bool | None = Query(default=None),
) -> TaskListResponse:
    filters = TaskFilters(
        responsible_id=responsible_id,
        candidate_id=candidate_id,
        is_completed=is_completed,
    )
    return await service.get_list(request, filters, page, page_size)


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу",
    dependencies=[Depends(require_permission("crm.candidates.edit"))],
)
async def create_task(
    data: TaskCreate,
    request: Request,
    service: Annotated[TaskService, Depends(_get_task_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    return await service.create(request, data)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Обновить задачу",
    dependencies=[Depends(require_permission("crm.candidates.edit"))],
)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    request: Request,
    service: Annotated[TaskService, Depends(_get_task_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    return await service.update(request, task_id, data)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить задачу",
    dependencies=[Depends(require_permission("crm.candidates.edit"))],
)
async def delete_task(
    task_id: uuid.UUID,
    request: Request,
    service: Annotated[TaskService, Depends(_get_task_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete(request, task_id)


@router.post(
    "/{task_id}/complete",
    response_model=TaskResponse,
    summary="Отметить задачу выполненной",
    dependencies=[Depends(require_permission("crm.candidates.edit"))],
)
async def complete_task(
    task_id: uuid.UUID,
    request: Request,
    service: Annotated[TaskService, Depends(_get_task_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    return await service.complete(request, task_id)
