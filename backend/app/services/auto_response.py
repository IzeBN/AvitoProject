"""
AutoResponseService — отправка автоматических ответов.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from app.repositories.messaging import MessagingRepository

if TYPE_CHECKING:
    from app.models.avito import AvitoAccount
    from app.services.avito_client import AvitoAPIClient

logger = logging.getLogger(__name__)


class AutoResponseService:
    def __init__(
        self,
        repo: MessagingRepository,
        avito_client: "AvitoAPIClient",
    ) -> None:
        self._repo = repo
        self._client = avito_client

    async def send_auto_response(
        self,
        account: "AvitoAccount",
        chat_id: str,
        avito_user_id: int,
        item_id: int,
    ) -> bool:
        """
        Отправить автоответ если есть активное правило.
        Сначала ищет ItemMessage, потом DefaultMessage.
        Возвращает True если сообщение отправлено.
        """
        rule = await self._repo.get_active_rule_for_item(
            account.org_id, account.id, item_id
        )
        if rule is None:
            return False

        # Определяем текст: rule.message → item → default
        message_text: str | None = rule.message if rule.message else None
        if not message_text:
            message_text = await self._resolve_message_text(
                account.org_id, account.id, item_id
            )
        if not message_text:
            logger.warning(
                "auto_response: no message text for account=%s item=%s",
                account.id,
                item_id,
            )
            return False

        try:
            await self._client.send_message(
                account, chat_id, avito_user_id, message_text
            )
            logger.info(
                "auto_response sent: account=%s chat=%s",
                account.id,
                chat_id,
            )
            return True
        except Exception:
            logger.exception(
                "auto_response failed: account=%s chat=%s",
                account.id,
                chat_id,
            )
            return False

    async def _resolve_message_text(
        self,
        org_id: uuid.UUID,
        account_id: uuid.UUID,
        item_id: int,
    ) -> str | None:
        # Приоритет: ItemMessage > DefaultMessage
        item_msg = await self._repo.get_item_message(org_id, item_id)
        if item_msg and item_msg.is_active:
            return item_msg.message

        default_msg = await self._repo.get_default_message(org_id, account_id)
        if default_msg:
            return default_msg.message

        return None
