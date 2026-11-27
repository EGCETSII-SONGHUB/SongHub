from flask import current_app
from flask_mail import Message

from app.features.email import mail


class EmailService:
    def send_email(self, recipient: str, subject: str, body: str, html: str | None = None) -> None:
        if not current_app.testing and not (
            current_app.config.get("MAIL_SERVER") and current_app.config.get("MAIL_DEFAULT_SENDER")
        ):
            raise RuntimeError("Email delivery requires MAIL_SERVER and MAIL_DEFAULT_SENDER configuration.")

        message = Message(
            subject=subject,
            recipients=[recipient],
            body=body,
            html=html,
        )
        mail.send(message)
