from app import db
from app.features.auth.services import AuthenticationService

PASSWORD = "testpass123"


def create_user(app, email, role="user"):
    with app.app_context():
        user = AuthenticationService().create_with_profile(
            email=email, password=PASSWORD, name="Test", surname=role.title()
        )
        user.role = role
        db.session.commit()
        return user.id


def login(client, email):
    response = client.post("/login", data={"email": email, "password": PASSWORD}, follow_redirects=False)
    assert response.status_code in (302, 303)