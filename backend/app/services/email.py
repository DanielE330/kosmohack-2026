"""Отправка писем через SMTP (Brevo relay).

Если `smtp_host`/`smtp_login`/`smtp_password` не заданы в окружении —
`send_confirmation_email` молча ничего не делает (не бросает исключение),
чтобы регистрация продолжала работать локально/в тестах без настоящей
почты, как и раньше (`email_confirmation_token` в ответе — по-прежнему
рабочий способ подтвердить почту, письмо это дублирует, а не заменяет).
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def send_confirmation_email(to_email: str, token: str) -> bool:
    if not (settings.smtp_host and settings.smtp_login and settings.smtp_password):
        logger.info("SMTP не настроен — письмо подтверждения не отправлено (%s)", to_email)
        return False

    link = f"{settings.frontend_base_url}/confirm-email?token={token}&email={to_email}"
    message = EmailMessage()
    message["Subject"] = "Подтвердите почту — SkyTime"
    message["From"] = settings.mail_from
    message["To"] = to_email
    message.set_content(
        "Здравствуйте!\n\n"
        "Подтвердите регистрацию в SkyTime, перейдя по ссылке:\n"
        f"{link}\n\n"
        "Если вы не регистрировались в SkyTime, просто проигнорируйте это письмо."
    )
    message.add_alternative(
        f"""
        <div style="font-family: sans-serif; max-width: 480px;">
          <h2 style="color:#0E2B2C;">SkyTime</h2>
          <p>Здравствуйте!</p>
          <p>Подтвердите регистрацию, перейдя по ссылке:</p>
          <p><a href="{link}" style="background:#0E2B2C;color:#F5F1E7;padding:10px 18px;
             border-radius:24px;text-decoration:none;display:inline-block;">
             Подтвердить почту</a></p>
          <p style="color:#666;font-size:12px;">Если вы не регистрировались в SkyTime —
             просто проигнорируйте это письмо.</p>
        </div>
        """,
        subtype="html",
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_login, settings.smtp_password)
            smtp.send_message(message)
        return True
    except Exception:  # noqa: BLE001 — почта не должна ронять регистрацию
        logger.exception("Не удалось отправить письмо подтверждения на %s", to_email)
        return False


def send_password_change_email(to_email: str, token: str) -> bool:
    """Подтверждение смены пароля — тот же принцип, что и
    `send_confirmation_email`: молча ничего не делает, если SMTP не
    настроен (токен из ответа `/auth/change-password` остаётся рабочим
    способом подтвердить смену)."""
    if not (settings.smtp_host and settings.smtp_login and settings.smtp_password):
        logger.info("SMTP не настроен — письмо смены пароля не отправлено (%s)", to_email)
        return False

    link = f"{settings.frontend_base_url}/confirm-password-change?token={token}"
    message = EmailMessage()
    message["Subject"] = "Подтвердите смену пароля — SkyTime"
    message["From"] = settings.mail_from
    message["To"] = to_email
    message.set_content(
        "Здравствуйте!\n\n"
        "Кто-то (надеемся, что вы) запросил смену пароля в SkyTime. "
        "Чтобы подтвердить новый пароль, перейдите по ссылке:\n"
        f"{link}\n\n"
        "Если вы не запрашивали смену пароля, просто проигнорируйте это письмо — "
        "текущий пароль останется без изменений."
    )
    message.add_alternative(
        f"""
        <div style="font-family: sans-serif; max-width: 480px;">
          <h2 style="color:#0E2B2C;">SkyTime</h2>
          <p>Здравствуйте!</p>
          <p>Кто-то (надеемся, что вы) запросил смену пароля. Подтвердите новый
             пароль, перейдя по ссылке:</p>
          <p><a href="{link}" style="background:#0E2B2C;color:#F5F1E7;padding:10px 18px;
             border-radius:24px;text-decoration:none;display:inline-block;">
             Подтвердить смену пароля</a></p>
          <p style="color:#666;font-size:12px;">Если вы не запрашивали смену пароля —
             просто проигнорируйте это письмо, текущий пароль останется без изменений.</p>
        </div>
        """,
        subtype="html",
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_login, settings.smtp_password)
            smtp.send_message(message)
        return True
    except Exception:  # noqa: BLE001 — почта не должна ронять смену пароля
        logger.exception("Не удалось отправить письмо смены пароля на %s", to_email)
        return False
