"""
MessagingRepository — шаблоны сообщений: дефолтные, по объявлению, авто-ответы, быстрые.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.messaging import AutoResponseRule, DefaultMessage, ItemMessage
from app.models.chat import FastAnswer


class MessagingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # DefaultMessage
    # ------------------------------------------------------------------

    async def get_default_message(
        self, org_id: uuid.UUID, account_id: uuid.UUID
    ) -> DefaultMessage | None:
        result = await self._db.execute(
            select(DefaultMessage).where(
                DefaultMessage.org_id == org_id,
                DefaultMessage.avito_account_id == account_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_default_message(
        self, org_id: uuid.UUID, account_id: uuid.UUID, message: str
    ) -> DefaultMessage:
        existing = await self.get_default_message(org_id, account_id)
        if existing:
            existing.message = message
            await self._db.flush()
            return existing

        obj = DefaultMessage(
            org_id=org_id,
            avito_account_id=account_id,
            message=message,
        )
        self._db.add(obj)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    # ------------------------------------------------------------------
    # ItemMessage
    # ------------------------------------------------------------------

    async def get_item_messages(self, org_id: uuid.UUID) -> list[ItemMessage]:
        result = await self._db.execute(
            select(ItemMessage)
            .where(ItemMessage.org_id == org_id)
            .order_by(ItemMessage.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_item_message(
        self, org_id: uuid.UUID, item_id: int
    ) -> ItemMessage | None:
        result = await self._db.execute(
            select(ItemMessage).where(
                ItemMessage.org_id == org_id,
                ItemMessage.avito_item_id == item_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_item_message(
        self,
        org_id: uuid.UUID,
        account_id: uuid.UUID,
        item_id: int,
        message: str,
    ) -> ItemMessage:
        existing = await self.get_item_message(org_id, item_id)
        if existing:
            existing.message = message
            await self._db.flush()
            return existing

        obj = ItemMessage(
            org_id=org_id,
            avito_account_id=account_id,
            avito_item_id=item_id,
            message=message,
        )
        self._db.add(obj)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    # ------------------------------------------------------------------
    # AutoResponseRule
    # ------------------------------------------------------------------

    async def get_auto_rules(self, org_id: uuid.UUID) -> list[AutoResponseRule]:
        result = await self._db.execute(
            select(AutoResponseRule)
            .where(AutoResponseRule.org_id == org_id)
            .order_by(AutoResponseRule.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_auto_rule_by_id(
        self, org_id: uuid.UUID, rule_id: uuid.UUID
    ) -> AutoResponseRule | None:
        result = await self._db.execute(
            select(AutoResponseRule).where(
                AutoResponseRule.org_id == org_id,
                AutoResponseRule.id == rule_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_rule_for_item(
        self,
        org_id: uuid.UUID,
        account_id: uuid.UUID,
        item_id: int,
        auto_type: str | None = None,
    ) -> AutoResponseRule | None:
        """
        Найти активное правило: сначала специфичное для item_id (в avito_item_ids),
        потом глобальное (avito_item_ids IS NULL).
        Если auto_type задан — фильтрует по нему.
        """
        from sqlalchemy import text as sa_text

        def _base_conditions():
            conds = [
                AutoResponseRule.org_id == org_id,
                AutoResponseRule.avito_account_id == account_id,
                AutoResponseRule.is_active.is_(True),
            ]
            if auto_type is not None:
                conds.append(AutoResponseRule.auto_type == auto_type)
            return conds

        # Правило с конкретным item_id в массиве avito_item_ids
        result = await self._db.execute(
            select(AutoResponseRule)
            .where(
                *_base_conditions(),
                AutoResponseRule.avito_item_ids.isnot(None),
                sa_text(":item_id = ANY(avito_item_ids)").bindparams(item_id=item_id),
            )
        )
        rule = result.scalar_one_or_none()
        if rule:
            return rule

        # Глобальное правило (без конкретных ID)
        result = await self._db.execute(
            select(AutoResponseRule).where(
                *_base_conditions(),
                AutoResponseRule.avito_item_ids.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create_auto_rule(self, rule: AutoResponseRule) -> AutoResponseRule:
        self._db.add(rule)
        await self._db.flush()
        await self._db.refresh(rule)
        return rule

    async def delete_auto_rule(self, rule: AutoResponseRule) -> None:
        await self._db.delete(rule)
        await self._db.flush()

    # ------------------------------------------------------------------
    # FastAnswer
    # ------------------------------------------------------------------

    async def get_fast_answers(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[FastAnswer]:
        result = await self._db.execute(
            select(FastAnswer)
            .where(
                FastAnswer.org_id == org_id,
                FastAnswer.user_id == user_id,
            )
            .order_by(FastAnswer.sort_order)
        )
        return list(result.scalars().all())

    async def get_fast_answer_by_id(
        self, org_id: uuid.UUID, user_id: uuid.UUID, answer_id: uuid.UUID
    ) -> FastAnswer | None:
        result = await self._db.execute(
            select(FastAnswer).where(
                FastAnswer.org_id == org_id,
                FastAnswer.user_id == user_id,
                FastAnswer.id == answer_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_fast_answer(self, answer: FastAnswer) -> FastAnswer:
        self._db.add(answer)
        await self._db.flush()
        await self._db.refresh(answer)
        return answer

    async def delete_fast_answer(self, answer: FastAnswer) -> None:
        await self._db.delete(answer)
        await self._db.flush()
