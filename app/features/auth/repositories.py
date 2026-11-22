from splent_framework.repositories.BaseRepository import BaseRepository

from app.features.auth.models import User


class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__(User)

    def create(self, commit: bool = True, **kwargs):
        password = kwargs.pop("password")
        instance = self.model(**kwargs)
        instance.set_password(password)
        self.session.add(instance)
        if commit:
            self.session.commit()
        else:
            self.session.flush()
        return instance

    def get_by_email(self, email: str):
        return self.model.query.filter_by(email=email).first()

    def list_all(self):
        return self.model.query.order_by(self.model.email).all()

    def get_user(self, user_id: int):
        return self.session.get(self.model, user_id)

    def count_by_role(self, role: str) -> int:
        return self.model.query.filter_by(role=role).count()
