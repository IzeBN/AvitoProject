"""
SMTP сервис для отправки email.
Использует aiosmtplib через fastapi-mail.
"""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


class SMTPService:
    """
    Сервис отправки email через SMTP.
    Рендерит HTML из Jinja2 шаблонов.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    @property
    def is_configured(self) -> bool:
        """Проверить что SMTP настроен."""
        return bool(self._settings.SMTP_HOST and self._settings.SMTP_USER)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        context: dict,
    ) -> bool:
        """
        Отправить email из шаблона.

        Args:
            to_email: адрес получателя
            subject: тема письма
            template_name: имя шаблона (без расширения)
            context: переменные для шаблона

        Returns:
            True если письмо успешно отправлено
        """
        if not self.is_configured:
            logger.warning(
                "SMTP not configured, skipping email to %s (subject: %s)",
                to_email,
                subject,
            )
            return False

        try:
            html_content = self._render_template(template_name, context)
            await self._send_raw(to_email, subject, html_content)
            logger.info("Email sent to %s (subject: %s)", to_email, subject)
            return True
        except Exception:
            logger.exception("Failed to send email to %s", to_email)
            return False

    def _render_template(self, template_name: str, context: dict) -> str:
        """Рендерить Jinja2 шаблон."""
        template_file = f"{template_name}.html" if not template_name.endswith(".html") else template_name
        template = self._jinja_env.get_template(template_file)
        return template.render(**context)

    async def _send_raw(self, to_email: str, subject: str, html_content: str) -> None:
        """Отправить HTML письмо через aiosmtplib."""
        import aiosmtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self._settings.SMTP_FROM_NAME} <{self._settings.SMTP_USER}>"
        msg["To"] = to_email

        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)

        smtp_params: dict = {
            "hostname": self._settings.SMTP_HOST,
            "port": self._settings.SMTP_PORT,
            "username": self._settings.SMTP_USER,
            "password": self._settings.SMTP_PASSWORD,
            "use_tls": self._settings.SMTP_SSL,
        }

        async with aiosmtplib.SMTP(**smtp_params) as smtp:
            if self._settings.SMTP_TLS and not self._settings.SMTP_SSL:
                await smtp.starttls()
            await smtp.send_message(msg)

    async def test_connection(self) -> bool:
        """Проверить подключение к SMTP серверу."""
        if not self.is_configured:
            return False
        try:
            import aiosmtplib

            smtp = aiosmtplib.SMTP(
                hostname=self._settings.SMTP_HOST,
                port=self._settings.SMTP_PORT,
                use_tls=self._settings.SMTP_SSL,
            )
            await smtp.connect()
            if self._settings.SMTP_TLS and not self._settings.SMTP_SSL:
                await smtp.starttls()
            await smtp.login(self._settings.SMTP_USER, self._settings.SMTP_PASSWORD)
            await smtp.quit()
            return True
        except Exception:
            logger.exception("SMTP connection test failed")
            return False
