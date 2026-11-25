import os

from flask import current_app, url_for
from flask_login import current_user, login_user
from flask_mail import Message
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from splent_framework.configuration.configuration import uploads_folder_name
from splent_framework.services.BaseService import BaseService

from app import db
from app.features.auth import mail
from app.features.auth.models import User
from app.features.auth.repositories import UserRepository
from app.features.profile.models import UserProfile
from app.features.profile.repositories import UserProfileRepository

EMAIL_VERIFICATION_SALT = "email-verification"


class AuthenticationService(BaseService):
    def __init__(self):
        super().__init__(UserRepository())
        self.user_profile_repository = UserProfileRepository()

    def login(self, email, password, remember=True):
        user = self.repository.get_by_email(email)
        if user is not None and user.check_password(password):
            login_user(user, remember=remember)
            return True
        return False

    def is_email_available(self, email: str) -> bool:
        return self.repository.get_by_email(email) is None

    def create_email_verification_token(self, user: User) -> str:
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        return serializer.dumps({"user_id": user.id, "email": user.email}, salt=EMAIL_VERIFICATION_SALT)

    def verify_email_token(self, token: str) -> User | None:
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        try:
            data = serializer.loads(
                token,
                salt=EMAIL_VERIFICATION_SALT,
                max_age=current_app.config.get("EMAIL_VERIFICATION_MAX_AGE", 3600),
            )
        except (BadSignature, SignatureExpired):
            return None

        if not isinstance(data, dict):
            return None
        user = self.repository.get_by_id(data.get("user_id"))
        if user is None or user.email != data.get("email"):
            return None
        if not user.email_verified:
            user.email_verified = True
            db.session.commit()
        return user

    def send_verification_email(self, user: User) -> None:
        if not current_app.testing and not (
            current_app.config.get("MAIL_SERVER") and current_app.config.get("MAIL_DEFAULT_SENDER")
        ):
            raise RuntimeError("Email verification requires MAIL_SERVER and MAIL_DEFAULT_SENDER configuration.")

        token = self.create_email_verification_token(user)
        verification_url = url_for("auth.verify_email", token=token, _external=True)
        message = Message(
            subject="Verify your email address",
            recipients=[user.email],
            body=f"Verify your email address by visiting this link:\n\n{verification_url}",
        )
        mail.send(message)

    def create_with_profile(self, **kwargs):
        try:
            email = kwargs.pop("email", None)
            password = kwargs.pop("password", None)
            name = kwargs.pop("name", None)
            surname = kwargs.pop("surname", None)

            if not email:
                raise ValueError("Email is required.")
            if not password:
                raise ValueError("Password is required.")
            if not name:
                raise ValueError("Name is required.")
            if not surname:
                raise ValueError("Surname is required.")

            user_data = {"email": email, "password": password}

            profile_data = {
                "name": name,
                "surname": surname,
            }

            user = self.create(commit=False, **user_data)
            profile_data["user_id"] = user.id
            self.user_profile_repository.create(**profile_data)
            self.repository.session.commit()
        except Exception as exc:
            self.repository.session.rollback()
            raise exc
        return user

    def get_authenticated_user(self) -> User | None:
        if current_user.is_authenticated:
            return current_user
        return None

    def get_authenticated_user_profile(self) -> UserProfile | None:
        if current_user.is_authenticated:
            return current_user.profile
        return None

    def temp_folder_by_user(self, user: User) -> str:
        return os.path.join(uploads_folder_name(), "temp", str(user.id))
