import time

import pytest

from app.features.auth.repositories import UserRepository
from app.features.auth.services import AuthenticationService

pytestmark = pytest.mark.service


def test_email_available_for_unused_address(test_app):
    with test_app.app_context():
        service = AuthenticationService()
        assert service.is_email_available("ghost@example.com") is True


def test_create_with_profile_persists_user(test_app):
    with test_app.app_context():
        service = AuthenticationService()
        user = service.create_with_profile(
            email="bob@example.com",
            password="bobpass",
            name="Bob",
            surname="Smith",
        )
        assert user.id is not None
        assert user.email_verified is False
        assert service.is_email_available("bob@example.com") is False


def test_email_verification_token_marks_user_verified(test_app):
    with test_app.app_context():
        service = AuthenticationService()
        user = service.create_with_profile(
            email="verify@example.com",
            password="pass",
            name="Verify",
            surname="User",
        )
        token = service.create_email_verification_token(user)

        verified_user = service.verify_email_token(token)

        assert verified_user.id == user.id
        assert UserRepository().get_by_id(user.id).email_verified is True


def test_expired_email_verification_token_is_rejected(test_app, monkeypatch):
    with test_app.app_context():
        service = AuthenticationService()
        user = service.create_with_profile(
            email="expired@example.com",
            password="pass",
            name="Expired",
            surname="User",
        )
        token = service.create_email_verification_token(user)
        original_time = time.time
        monkeypatch.setattr("itsdangerous.timed.time.time", lambda: original_time() + 3601)

        assert service.verify_email_token(token) is None
        assert UserRepository().get_by_id(user.id).email_verified is False


def test_manipulated_email_verification_token_is_rejected(test_app):
    with test_app.app_context():
        service = AuthenticationService()
        user = service.create_with_profile(
            email="tampered@example.com",
            password="pass",
            name="Tampered",
            surname="User",
        )
        token = service.create_email_verification_token(user)

        assert service.verify_email_token(token + "x") is None
        assert UserRepository().get_by_id(user.id).email_verified is False
