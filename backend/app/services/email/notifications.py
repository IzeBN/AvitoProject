"""
Сервис email уведомлений.
Предоставляет высокоуровневые методы для отправки конкретных уведомлений.
"""

import logging

from app.config import Settings
from app.services.email.smtp import SMTPService

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """
    Высокоуровневый сервис уведомлений.
    Все методы принимают бизнес-параметры и сами формируют контекст шаблона.
    """

    def __init__(self, settings: Settings) -> None:
        self._smtp = SMTPService(settings)
        self._settings = settings

    async def send_welcome(self, email: str, full_name: str, org_name: str) -> bool:
        """Отправить приветственное письмо после регистрации."""
        return await self._smtp.send_email(
            to_email=email,
            subject=f"Добро пожаловать в {self._settings.APP_NAME}!",
            template_name="base",
            context={
                "accent_color": "#6366f1",
                "badge_label": "Регистрация",
                "badge_icon": "✓",
                "title": f"Добро пожаловать, {full_name}!",
                "body": (
                    f"Ваш аккаунт в <strong>{self._settings.APP_NAME}</strong> успешно создан. "
                    f"Организация <strong>{org_name}</strong> зарегистрирована и готова к работе."
                ),
                "cta_text": "Войти в систему",
                "cta_url": "#",
                "footer_text": (
                    f"Вы получили это письмо, так как зарегистрировались в {self._settings.APP_NAME}. "
                    "Если это не вы — просто проигнорируйте письмо."
                ),
                "product_name": self._settings.APP_NAME,
            },
        )

    async def send_password_reset(
        self,
        email: str,
        full_name: str,
        reset_url: str,
    ) -> bool:
        """Отправить письмо для сброса пароля."""
        return await self._smtp.send_email(
            to_email=email,
            subject=f"{self._settings.APP_NAME} — сброс пароля",
            template_name="base",
            context={
                "accent_color": "#ef4444",
                "badge_label": "Сброс пароля",
                "badge_icon": "🔒",
                "title": "Сброс пароля",
                "body": (
                    f"Здравствуйте, <strong>{full_name}</strong>!<br><br>"
                    "Мы получили запрос на сброс пароля для вашего аккаунта. "
                    "Нажмите кнопку ниже для создания нового пароля. "
                    "Ссылка действительна 30 минут."
                ),
                "cta_text": "Сбросить пароль",
                "cta_url": reset_url,
                "secondary_text": "Если вы не запрашивали сброс пароля — просто проигнорируйте письмо.",
                "footer_text": f"© {self._settings.APP_NAME}",
                "product_name": self._settings.APP_NAME,
            },
        )

    async def send_invite(
        self,
        email: str,
        inviter_name: str,
        org_name: str,
        role: str,
        invite_url: str,
        temp_password: str | None = None,
    ) -> bool:
        """Отправить приглашение в организацию."""
        details = [
            {"label": "Организация", "value": org_name},
            {"label": "Роль", "value": role},
        ]
        highlight = {"label": "Временный пароль", "value": temp_password} if temp_password else None

        return await self._smtp.send_email(
            to_email=email,
            subject=f"{inviter_name} приглашает вас в {org_name}",
            template_name="base",
            context={
                "accent_color": "#10b981",
                "badge_label": "Приглашение",
                "badge_icon": "📨",
                "title": "Вас приглашают в команду",
                "body": (
                    f"<strong>{inviter_name}</strong> приглашает вас присоединиться "
                    f"к организации <strong>{org_name}</strong> в {self._settings.APP_NAME}."
                ),
                "details": details,
                "highlight": highlight,
                "cta_text": "Принять приглашение",
                "cta_url": invite_url,
                "footer_text": f"© {self._settings.APP_NAME}",
                "product_name": self._settings.APP_NAME,
            },
        )

    async def send_employee_invite(
        self,
        email: str,
        full_name: str,
        org_name: str,
        temp_password: str,
    ) -> bool:
        """
        Отправить приветственное письмо новому сотруднику с временным паролем.
        Вызывается из UserManagementService.invite_user.
        """
        return await self._smtp.send_email(
            to_email=email,
            subject=f"Добро пожаловать в {org_name} — {self._settings.APP_NAME}",
            template_name="base",
            context={
                "accent_color": "#6366f1",
                "badge_label": "Приглашение",
                "badge_icon": "✓",
                "title": f"Добро пожаловать, {full_name}!",
                "body": (
                    f"Вас добавили в организацию <strong>{org_name}</strong> "
                    f"в системе {self._settings.APP_NAME}."
                ),
                "details": [
                    {"label": "Логин (email)", "value": email},
                ],
                "highlight": {"label": "Временный пароль", "value": temp_password},
                "cta_text": "Войти в систему",
                "cta_url": "#",
                "secondary_text": "Пожалуйста, смените пароль после первого входа.",
                "footer_text": f"© {self._settings.APP_NAME}",
                "product_name": self._settings.APP_NAME,
            },
        )
