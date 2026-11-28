import pytest

from app import db
from app.features.auth.models import Role, User
from tests.auth_helpers import create_user, login

pytestmark = pytest.mark.integration


def _role_of(app, user_id):
    with app.application.app_context() if hasattr(app, "application") else app.app_context():
        return db.session.get(User, user_id).role


def test_anonymous_is_redirected_to_login(test_client):
    response = test_client.get("/admin/users")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("role", [Role.USER, Role.CURATOR])
def test_non_admins_get_403(test_client, role):
    create_user(test_client.application, "x@example.com", role)
    login(test_client, "x@example.com")
    assert test_client.get("/admin/users").status_code == 403


def test_admin_sees_all_users(test_client):
    create_user(test_client.application, "boss@example.com", Role.ADMIN)
    create_user(test_client.application, "bob@example.com", Role.USER)
    login(test_client, "boss@example.com")
    response = test_client.get("/admin/users")
    assert response.status_code == 200
    assert b"boss@example.com" in response.data and b"bob@example.com" in response.data


def test_admin_can_change_a_role(test_client):
    create_user(test_client.application, "boss@example.com", Role.ADMIN)
    bob = create_user(test_client.application, "bob@example.com", Role.USER)
    login(test_client, "boss@example.com")
    response = test_client.post(f"/admin/users/{bob}/role", data={"role": Role.CURATOR})
    assert response.status_code == 302
    assert _role_of(test_client, bob) == Role.CURATOR


def test_invalid_role_is_ignored(test_client):
    create_user(test_client.application, "boss@example.com", Role.ADMIN)
    bob = create_user(test_client.application, "bob@example.com", Role.USER)
    login(test_client, "boss@example.com")
    test_client.post(f"/admin/users/{bob}/role", data={"role": "superman"})
    assert _role_of(test_client, bob) == Role.USER


def test_non_admin_cannot_escalate_privileges(test_client):
    mallory = create_user(test_client.application, "mallory@example.com", Role.USER)
    login(test_client, "mallory@example.com")
    response = test_client.post(f"/admin/users/{mallory}/role", data={"role": Role.ADMIN})
    assert response.status_code == 403
    assert _role_of(test_client, mallory) == Role.USER


def test_last_admin_cannot_be_demoted(test_client):
    boss = create_user(test_client.application, "boss@example.com", Role.ADMIN)
    login(test_client, "boss@example.com")
    test_client.post(f"/admin/users/{boss}/role", data={"role": Role.USER})
    assert _role_of(test_client, boss) == Role.ADMIN
