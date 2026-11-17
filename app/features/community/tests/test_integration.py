"""HTTP integration tests for the community feature via the Flask test client."""

from datetime import datetime, timezone
from io import BytesIO

import pytest

from app.features.auth.repositories import UserRepository
from app.features.community.repositories import CommunityRepository
from app.features.dataset.models import PublicationType
from app.features.dataset.repositories import DataSetRepository, DSMetaDataRepository

pytestmark = pytest.mark.integration


def _signup(test_client, email="owner@example.com", password="password123", name="Ada", surname="Lovelace"):
    """Register and log in a user via the auth blueprint, returning their user ID."""
    test_client.get("/logout", follow_redirects=False)
    response = test_client.post(
        "/signup/",
        data={"email": email, "password": password, "name": name, "surname": surname},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    with test_client.application.app_context():
        return UserRepository().get_by_email(email).id


def _login(test_client, email, password="password123"):
    test_client.get("/logout", follow_redirects=False)
    response = test_client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


def _make_dataset(user_id: int, title: str = "Sample dataset", doi: str | None = None):
    meta = DSMetaDataRepository().create(
        title=title,
        description=f"Description for {title}",
        publication_type=PublicationType.DATA_MANAGEMENT_PLAN,
        dataset_doi=doi,
        deposition_id=10 if doi else None,
        tags="music,spotify",
    )
    return DataSetRepository().create(
        user_id=user_id,
        ds_meta_data_id=meta.id,
        created_at=datetime.now(timezone.utc),
    )


def test_list_communities_renders_empty_and_populated_states(test_client):
    empty_resp = test_client.get("/community")
    assert empty_resp.status_code == 200
    assert "No communities yet" in empty_resp.get_data(as_text=True)

    _signup(test_client, email="list-creator@example.com")
    create_resp = test_client.post(
        "/community/create",
        data={"name": "Electronic Hub", "description": "Electronic music datasets"},
        follow_redirects=False,
    )
    assert create_resp.status_code in (302, 303)

    list_resp = test_client.get("/community")
    body = list_resp.get_data(as_text=True)
    assert list_resp.status_code == 200
    assert "Electronic Hub" in body
    assert "Electronic music datasets" in body
    assert "0 datasets" in body


def test_create_community_requires_login(test_client):
    get_resp = test_client.get("/community/create", follow_redirects=False)
    assert get_resp.status_code == 302
    assert "/login" in get_resp.headers["Location"]

    post_resp = test_client.post(
        "/community/create",
        data={"name": "Anon Hub", "description": "Should not be created"},
        follow_redirects=False,
    )
    assert post_resp.status_code == 302
    assert "/login" in post_resp.headers["Location"]


def test_create_community_with_logo_serves_logo_and_validates_inputs(test_client, monkeypatch, tmp_path):
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))
    creator_id = _signup(test_client, email="logo-creator@example.com")

    get_form = test_client.get("/community/create")
    assert get_form.status_code == 200
    assert 'name="name"' in get_form.get_data(as_text=True)

    # Reject disallowed logo extension without persisting a community.
    bad_logo = test_client.post(
        "/community/create",
        data={
            "name": "Bad Logo Hub",
            "description": "Invalid file test",
            "logo": (BytesIO(b"plain text"), "notes.txt"),
        },
        content_type="multipart/form-data",
    )
    assert bad_logo.status_code == 200
    assert "Logo must be an image file" in bad_logo.get_data(as_text=True)
    with test_client.application.app_context():
        assert CommunityRepository().get_by_name("Bad Logo Hub") is None

    # Create valid community with PNG logo.
    created = test_client.post(
        "/community/create",
        data={
            "name": "Indie Sound Hub",
            "description": "Independent music collections",
            "logo": (BytesIO(b"\x89PNG\r\n\x1a\nfake"), "indie.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert created.status_code in (302, 303)

    with test_client.application.app_context():
        community = CommunityRepository().get_by_name("Indie Sound Hub")
        assert community is not None
        assert community.creator_id == creator_id
        assert [c.id for c in community.curators] == [creator_id]
        logo_filename = community.logo
        community_id = community.id

    detail_resp = test_client.get(f"/community/{community_id}")
    assert detail_resp.status_code == 200
    detail_body = detail_resp.get_data(as_text=True)
    assert "Indie Sound Hub" in detail_body
    assert "Lovelace, Ada" in detail_body
    assert f"/community/logos/{logo_filename}" in detail_body

    logo_resp = test_client.get(f"/community/logos/{logo_filename}")
    assert logo_resp.status_code == 200
    assert logo_resp.data == b"\x89PNG\r\n\x1a\nfake"

    # Duplicate name is rejected.
    dup = test_client.post(
        "/community/create",
        data={"name": "Indie Sound Hub", "description": "Duplicate"},
    )
    assert dup.status_code == 200
    assert "already exists" in dup.get_data(as_text=True)


def test_community_detail_returns_404_for_unknown_id(test_client):
    assert test_client.get("/community/99999").status_code == 404


def test_edit_community_restricted_to_curators_and_preserves_logo(test_client, monkeypatch, tmp_path):
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))

    anon_resp = test_client.get("/community/1/edit", follow_redirects=False)
    assert anon_resp.status_code == 302
    assert "/login" in anon_resp.headers["Location"]

    _signup(test_client, email="curator@example.com")
    test_client.post(
        "/community/create",
        data={
            "name": "Classical Hub",
            "description": "Original description",
            "logo": (BytesIO(b"\x89PNG\r\n\x1a\norig"), "classical.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    with test_client.application.app_context():
        community = CommunityRepository().get_by_name("Classical Hub")
        community_id = community.id
        original_logo = community.logo

    # Another logged-in non-curator receives 403 on both GET and POST.
    _signup(test_client, email="intruder@example.com", name="Bob", surname="Other")
    assert test_client.get(f"/community/{community_id}/edit").status_code == 403
    forbidden_post = test_client.post(
        f"/community/{community_id}/edit",
        data={"name": "Hacked", "description": "Hacked"},
    )
    assert forbidden_post.status_code == 403
    with test_client.application.app_context():
        assert CommunityRepository().get_by_id(community_id).name == "Classical Hub"

    # Log back in as curator and edit without uploading a new logo.
    _login(test_client, "curator@example.com")
    edit_page = test_client.get(f"/community/{community_id}/edit")
    assert edit_page.status_code == 200
    assert 'value="Classical Hub"' in edit_page.get_data(as_text=True)

    updated = test_client.post(
        f"/community/{community_id}/edit",
        data={"name": "Symphonic Hub", "description": "Updated description"},
        follow_redirects=False,
    )
    assert updated.status_code in (302, 303)
    with test_client.application.app_context():
        reloaded = CommunityRepository().get_by_id(community_id)
        assert reloaded.name == "Symphonic Hub"
        assert reloaded.description == "Updated description"
        assert reloaded.logo == original_logo


def test_only_dataset_owner_can_add_dataset_to_community(test_client):
    curator_id = _signup(test_client, email="comm-curator@example.com", name="Clara", surname="Curator")
    test_client.post(
        "/community/create",
        data={"name": "SoundHub Community", "description": "Shared music data"},
        follow_redirects=False,
    )
    with test_client.application.app_context():
        community_id = CommunityRepository().get_by_name("SoundHub Community").id

    owner_id = _signup(test_client, email="ds-owner@example.com", name="Oscar", surname="Owner")
    with test_client.application.app_context():
        owner_dataset_id = _make_dataset(owner_id, title="Top Hits 2026", doi="10.1234/top-hits").id
        curator_dataset_id = _make_dataset(curator_id, title="Curator Own Dataset").id

    # Anonymous user is redirected to login.
    test_client.get("/logout", follow_redirects=False)
    anon_add = test_client.post(
        f"/community/{community_id}/datasets/add",
        data={"dataset_id": owner_dataset_id},
        follow_redirects=False,
    )
    assert anon_add.status_code == 302
    assert "/login" in anon_add.headers["Location"]

    # Community curator CANNOT add a dataset owned by someone else -> 403 Forbidden.
    _login(test_client, "comm-curator@example.com")
    curator_attempt = test_client.post(
        f"/community/{community_id}/datasets/add",
        data={"dataset_id": owner_dataset_id},
        follow_redirects=False,
    )
    assert curator_attempt.status_code == 403
    with test_client.application.app_context():
        assert CommunityRepository().get_by_id(community_id).datasets == []

    # Missing dataset returns 404.
    assert (
        test_client.post(
            f"/community/{community_id}/datasets/add",
            data={"dataset_id": 99999},
            follow_redirects=False,
        ).status_code
        == 404
    )

    # Dataset owner CAN add their own dataset -> 302 and displayed on community & dataset pages.
    _login(test_client, "ds-owner@example.com")
    owner_attempt = test_client.post(
        f"/community/{community_id}/datasets/add",
        data={"dataset_id": owner_dataset_id},
        follow_redirects=False,
    )
    assert owner_attempt.status_code in (302, 303)

    # Owner cannot add the curator's dataset either -> 403.
    owner_on_theirs = test_client.post(
        f"/community/{community_id}/datasets/add",
        data={"dataset_id": curator_dataset_id},
        follow_redirects=False,
    )
    assert owner_on_theirs.status_code == 403

    community_page = test_client.get(f"/community/{community_id}")
    assert community_page.status_code == 200
    assert "Top Hits 2026" in community_page.get_data(as_text=True)

    dataset_page = test_client.get("/doi/10.1234/top-hits/")
    assert dataset_page.status_code == 200
    assert "SoundHub Community" in dataset_page.get_data(as_text=True)

    # Owner can remove their dataset from the community.
    remove_resp = test_client.post(
        f"/community/{community_id}/datasets/{owner_dataset_id}/remove",
        follow_redirects=False,
    )
    assert remove_resp.status_code in (302, 303)
    with test_client.application.app_context():
        assert CommunityRepository().get_by_id(community_id).datasets == []


def test_manage_curators_by_email_and_permissions(test_client):
    creator_id = _signup(test_client, email="lead-curator@example.com", name="Lead", surname="Curator")
    test_client.post(
        "/community/create",
        data={"name": "Curated Hub", "description": "Testing curator UI"},
        follow_redirects=False,
    )
    with test_client.application.app_context():
        community_id = CommunityRepository().get_by_name("Curated Hub").id

    second_id = _signup(test_client, email="second-user@example.com", name="Second", surname="User")

    # Anonymous visitors redirect to /login.
    test_client.get("/logout", follow_redirects=False)
    anon_add = test_client.post(
        f"/community/{community_id}/curators/add",
        data={"email": "second-user@example.com"},
        follow_redirects=False,
    )
    assert anon_add.status_code == 302
    assert "/login" in anon_add.headers["Location"]

    anon_remove = test_client.post(
        f"/community/{community_id}/curators/{creator_id}/remove",
        follow_redirects=False,
    )
    assert anon_remove.status_code == 302
    assert "/login" in anon_remove.headers["Location"]

    # Non-curator gets 403 on add and remove.
    _login(test_client, "second-user@example.com")
    assert (
        test_client.post(
            f"/community/{community_id}/curators/add",
            data={"email": "second-user@example.com"},
            follow_redirects=False,
        ).status_code
        == 403
    )
    assert (
        test_client.post(
            f"/community/{community_id}/curators/{creator_id}/remove",
            follow_redirects=False,
        ).status_code
        == 403
    )

    # Creator cannot remove themselves when they are the sole curator.
    _login(test_client, "lead-curator@example.com")
    sole_remove = test_client.post(
        f"/community/{community_id}/curators/{creator_id}/remove",
        follow_redirects=True,
    )
    assert sole_remove.status_code == 200
    assert "at least one curator" in sole_remove.get_data(as_text=True)
    with test_client.application.app_context():
        assert [c.id for c in CommunityRepository().get_by_id(community_id).curators] == [creator_id]

    # Unknown email flashes an error and keeps curators unchanged.
    unknown_add = test_client.post(
        f"/community/{community_id}/curators/add?next=edit",
        data={"email": "nobody@example.com"},
        follow_redirects=True,
    )
    assert unknown_add.status_code == 200
    assert "No user found" in unknown_add.get_data(as_text=True)

    # Adding a registered user grants them curator privileges (edit access).
    added_resp = test_client.post(
        f"/community/{community_id}/curators/add",
        data={"email": "second-user@example.com"},
        follow_redirects=False,
    )
    assert added_resp.status_code in (302, 303)
    with test_client.application.app_context():
        curator_ids = {c.id for c in CommunityRepository().get_by_id(community_id).curators}
        assert curator_ids == {creator_id, second_id}

    _login(test_client, "second-user@example.com")
    assert test_client.get(f"/community/{community_id}/edit").status_code == 200

    # Lead curator removes the second curator, revoking edit access.
    _login(test_client, "lead-curator@example.com")
    removed_resp = test_client.post(
        f"/community/{community_id}/curators/{second_id}/remove?next=edit",
        follow_redirects=False,
    )
    assert removed_resp.status_code in (302, 303)
    assert f"/community/{community_id}/edit" in removed_resp.headers["Location"]

    _login(test_client, "second-user@example.com")
    assert test_client.get(f"/community/{community_id}/edit").status_code == 403
