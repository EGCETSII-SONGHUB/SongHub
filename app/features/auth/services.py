import os

from flask import current_app, url_for
from flask_login import current_user, login_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from splent_framework.configuration.configuration import uploads_folder_name
from splent_framework.services.BaseService import BaseService

from app.features.auth.models import Role, User
from app import db
from app.features.auth.repositories import UserRepository
from app.features.email.services import EmailService
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
        token = self.create_email_verification_token(user)
        verification_url = url_for("auth.verify_email", token=token, _external=True)
        EmailService().send_email(
            recipient=user.email,
            subject="Welcome to UVLHub - verify your email address",
            body=(
                "Welcome to UVLHub!\n\n" "Verify your email address by visiting this link:\n\n" f"{verification_url}"
            ),
        )

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

    def list_users(self):
        return self.repository.list_all()

    def get_user(self, user_id: int):
        return self.repository.get_user(user_id)

    def change_role(self, user: User, role: str) -> User:
        if role not in Role.ALL:
            raise ValueError(f"Invalid role: {role}")
        if user.role == Role.ADMIN and role != Role.ADMIN and self.repository.count_by_role(Role.ADMIN) <= 1:
            raise ValueError("Cannot remove the last administrator.")
        user.role = role
        self.repository.session.commit()
        return user
