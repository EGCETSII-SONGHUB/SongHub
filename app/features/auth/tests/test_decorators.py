import pytest
from flask import Flask
from flask_login import LoginManager, login_user

from app.features.auth.decorators import role_required
from app.features.auth.models import Role, User

pytestmark = pytest.mark.unit


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", TESTING=True)
    users = {}
    login_manager = LoginManager(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        return users.get(int(user_id))

    @app.route("/login")
    def login():
        return "login page"

    @app.route("/_as/<role>")
    def _as(role):
        user = User(id=1, email=f"{role}@example.com", role=role)
        users[1] = user
        login_user(user)
        return "ok"

    @app.route("/admin-only")
    @role_required(Role.ADMIN)
    def admin_only():
        return "admin area"

    @app.route("/curator-area")
    @role_required(Role.CURATOR)
    def curator_area():
        return "curator area"

    return app.test_client()


@pytest.mark.parametrize("role, expected", [(Role.ADMIN, 200), (Role.CURATOR, 403), (Role.USER, 403)])
def test_admin_only_route(client, role, expected):
    client.get(f"/_as/{role}")
    assert client.get("/admin-only").status_code == expected


@pytest.mark.parametrize("role, expected", [(Role.ADMIN, 200), (Role.CURATOR, 200), (Role.USER, 403)])
def test_curator_route_also_admits_admin(client, role, expected):
    client.get(f"/_as/{role}")
    assert client.get("/curator-area").status_code == expected


@pytest.mark.parametrize("path", ["/admin-only", "/curator-area"])
def test_anonymous_is_redirected_to_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_unknown_role_is_rejected_at_decoration_time():
    with pytest.raises(ValueError):
        role_required("superman")


def test_at_least_one_role_is_required():
    with pytest.raises(ValueError):
        role_required()
