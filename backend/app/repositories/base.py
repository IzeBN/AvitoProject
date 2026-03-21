"""
Базовый репозиторий с CRUD операциями для SQLAlchemy 2.0.
"""

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Базовый репозиторий с типовыми CRUD операциями.
    Наследуйте и передавайте тип модели через Generic.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, record_id: uuid.UUID) -> ModelT | None:
        """Получить запись по первичному ключу."""
        return await self._session.get(self.model, record_id)

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ModelT]:
        """Получить список записей с пагинацией."""
        result = await self._session.execute(
            select(self.model).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        """Количество записей в таблице."""
        result = await self._session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()

    async def create(self, **kwargs: Any) -> ModelT:
        """Создать новую запись."""
        instance = self.model(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def update(self, instance: ModelT, **kwargs: Any) -> ModelT:
        """Обновить поля существующей записи."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        """Физически удалить запись."""
        await self._session.delete(instance)
        await self._session.flush()

    async def save(self, instance: ModelT) -> ModelT:
        """Сохранить (add + flush + refresh) экземпляр модели."""
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance
