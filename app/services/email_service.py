"""
Transactional email service.

Provider-agnostic abstraction with two backends selected by settings.EMAIL_BACKEND:

* console (default) — prints the message (and any action link) to stdout. Ideal for
  local development and tests; nothing leaves the machine.
* smtp             — sends via the configured SMTP_* server.

All templated helpers funnel through `send()` so adding an API provider (SES,
SendGrid, Postmark) later means implementing one method.
"""
import logging
import smtplib
from email.mime.text import MIMEText

from app.core.settings import settings

logger = logging.getLogger("swarmwarm.email")


class EmailService:
    def __init__(self):
        self.backend = settings.EMAIL_BACKEND.lower()
        self.sender = settings.EMAIL_FROM
        self.base_url = settings.PUBLIC_BASE_URL.rstrip("/")

    def send(self, to: str, subject: str, body: str) -> bool:
        if self.backend == "smtp" and settings.SMTP_HOST:
            return self._send_smtp(to, subject, body)
        # console backend — print so the message/link is always visible in dev stdout
        print(
            f"\n[EMAIL:console] to={to} | subject={subject}\n"
            f"{'-' * 60}\n{body}\n{'-' * 60}\n",
            flush=True,
        )
        return True

    def _send_smtp(self, to: str, subject: str, body: str) -> bool:
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.sender
            msg["To"] = to
            if settings.SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
            else:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as exc:  # never let email failures break the request flow
            logger.error("SMTP email send failed to %s: %s", to, exc)
            return False

    # ----- templated helpers -----
    def send_verification(self, to: str, token: str) -> bool:
        link = f"{self.base_url}/api/v1/auth/verify-email?token={token}"
        body = (
            "Welcome to SwarmWarm!\n\n"
            "Confirm your email address to activate your account:\n"
            f"{link}\n\n"
            "If you did not sign up, you can ignore this message."
        )
        return self.send(to, "Verify your SwarmWarm account", body)

    def send_password_reset(self, to: str, token: str) -> bool:
        link = f"{self.base_url}/api/v1/auth/password/reset?token={token}"
        body = (
            "We received a request to reset your SwarmWarm password.\n\n"
            f"Reset it here (valid for 1 hour):\n{link}\n\n"
            "If you did not request this, no action is needed."
        )
        return self.send(to, "Reset your SwarmWarm password", body)

    def send_invitation(self, to: str, token: str, org_name: str) -> bool:
        link = f"{self.base_url}/api/v1/orgs/invitations/accept?token={token}"
        body = (
            f"You have been invited to join the '{org_name}' workspace on SwarmWarm.\n\n"
            f"Accept the invitation:\n{link}\n\n"
            "This invitation will expire in 7 days."
        )
        return self.send(to, f"You're invited to {org_name} on SwarmWarm", body)


email_service = EmailService()
