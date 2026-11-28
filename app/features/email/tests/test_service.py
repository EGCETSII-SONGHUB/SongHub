from unittest.mock import Mock

import pytest
from flask import Flask

from app.features.email import mail
from app.features.email.services import EmailService

pytestmark = pytest.mark.unit


def test_send_email_uses_flask_mail(monkeypatch):
    app = Flask(__name__)
    app.config.update(
        MAIL_SERVER="localhost",
        MAIL_DEFAULT_SENDER="noreply@example.com",
        TESTING=False,
    )
    mail.init_app(app)
    send = Mock()
    monkeypatch.setattr(mail, "send", send)

    with app.app_context():
        EmailService().send_email(
            recipient="user@example.com",
            subject="Welcome",
            body="Welcome to UVLHub.",
        )

    message = send.call_args.args[0]
    assert message.subject == "Welcome"
    assert message.recipients == ["user@example.com"]
    assert message.body == "Welcome to UVLHub."
