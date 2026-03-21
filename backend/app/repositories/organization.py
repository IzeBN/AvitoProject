"""
Репозиторий организаций.
"""

import re

from sqlalchemy import select

from app.models.auth import Organization
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Репозиторий для работы с организациями."""

    model = Organization

    async def get_by_slug(self, slug: str) -> Organization | None:
        """Найти организацию по slug."""
        result = await self._session.execute(
            select(Organization).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        """Проверить что slug уже занят."""
        result = await self._session.execute(
            select(Organization.id).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none() is not None

    async def generate_unique_slug(self, name: str) -> str:
        """
        Сгенерировать уникальный slug из названия организации.
        Если slug занят — добавляет числовой суффикс.
        """
        base_slug = self._slugify(name)
        slug = base_slug
        counter = 1

        while await self.slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    @staticmethod
    def _slugify(text: str) -> str:
        """
        Преобразовать текст в slug.
        Кириллица транслитерируется, пробелы → дефисы.
        """
        # Транслитерация кириллицы
        translit_map = {
            "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
            "е": "e", "ё": "yo", "ж": "zh", "з": "z", "и": "i",
            "й": "j", "к": "k", "л": "l", "м": "m", "н": "n",
            "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
            "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
            "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
            "э": "e", "ю": "yu", "я": "ya",
        }
        text = text.lower()
        result = []
        for char in text:
            result.append(translit_map.get(char, char))
        text = "".join(result)

        # Оставляем только буквы, цифры и дефисы
        text = re.sub(r"[^a-z0-9\s-]", "", text)
        # Пробелы → дефисы
        text = re.sub(r"[\s_]+", "-", text)
        # Убираем дублирующиеся дефисы
        text = re.sub(r"-+", "-", text)
        text = text.strip("-")

        # Ограничиваем длину
        return text[:90] if text else "org"
