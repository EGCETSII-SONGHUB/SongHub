"""Service-level tests for the community feature against a real database."""

import os
from datetime import datetime, timezone
from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from app.features.auth.repositories import UserRepository
from app.features.community.forms import CommunityForm
from app.features.community.seeders import CommunitySeeder
from app.features.community.services import CommunityService
from app.features.dataset.models import PublicationType
from app.features.dataset.repositories import DataSetRepository, DSMetaDataRepository

pytestmark = pytest.mark.service


def _make_user(email: str):
    return UserRepository().create(email=email, password="secret")


def _make_dataset(user, title: str):
    meta = DSMetaDataRepository().create(
        title=title,
        description=f"Description for {title}",
        publication_type=PublicationType.DATA_MANAGEMENT_PLAN,
    )
    return DataSetRepository().create(
        user_id=user.id,
        ds_meta_data_id=meta.id,
        created_at=datetime.now(timezone.utc),
    )


def _image_upload(filename: str = "logo.png", content: bytes = b"fake-png-bytes") -> FileStorage:
    return FileStorage(stream=BytesIO(content), filename=filename, content_type="image/png")


def test_create_community_assigns_creator_as_initial_curator_and_saves_logo(
    test_app, clean_database, monkeypatch, tmp_path
):
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))
    with test_app.app_context():
        creator = _make_user("creator@example.com")
        service = CommunityService()

        data = {"name": "  Acoustic Archive  ", "description": "  Curated acoustic datasets  "}
        with test_app.test_request_context("/community/create", method="POST", data=data):
            community, errors = service.create_community(
                CommunityForm(),
                creator=creator,
                logo_file=_image_upload("crest.png"),
            )

        assert errors is None
        assert community is not None
        assert community.name == "Acoustic Archive"
        assert community.description == "Curated acoustic datasets"
        assert community.creator_id == creator.id
        assert [c.id for c in community.curators] == [creator.id]
        assert community.is_curator(creator) is True
        assert community.logo is not None
        assert os.path.isfile(os.path.join(service.logos_directory(), community.logo))


def test_create_community_rejects_duplicate_name_and_invalid_logo(test_app, clean_database):
    with test_app.app_context():
        creator = _make_user("dup@example.com")
        service = CommunityService()

        with test_app.test_request_context(
            "/community/create", method="POST", data={"name": "Jazz Hub", "description": "Jazz datasets"}
        ):
            first, errors = service.create_community(CommunityForm(), creator=creator)
        assert errors is None
        assert first is not None

        with test_app.test_request_context(
            "/community/create", method="POST", data={"name": "Jazz Hub", "description": "Duplicate"}
        ):
            dup, dup_errors = service.create_community(CommunityForm(), creator=creator)
        assert dup is None
        assert "name" in dup_errors

        with test_app.test_request_context(
            "/community/create", method="POST", data={"name": "Rock Hub", "description": "Rock datasets"}
        ):
            bad_logo, logo_errors = service.create_community(
                CommunityForm(),
                creator=creator,
                logo_file=_image_upload("readme.txt", b"not-an-image"),
            )
        assert bad_logo is None
        assert "logo" in logo_errors


def test_list_communities_returns_created_communities(test_app, clean_database):
    with test_app.app_context():
        creator = _make_user("lister@example.com")
        service = CommunityService()

        for idx in range(2):
            with test_app.test_request_context(
                "/community/create",
                method="POST",
                data={"name": f"Community {idx}", "description": f"Desc {idx}"},
            ):
                service.create_community(CommunityForm(), creator=creator)

        listed = service.list_communities()
        assert len(listed) == 2
        assert {c.name for c in listed} == {"Community 0", "Community 1"}


def test_update_community_curator_can_edit_and_preserves_or_replaces_logo(
    test_app, clean_database, monkeypatch, tmp_path
):
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))
    with test_app.app_context():
        curator = _make_user("editor@example.com")
        outsider = _make_user("outsider@example.com")
        service = CommunityService()

        with test_app.test_request_context(
            "/community/create", method="POST", data={"name": "Original", "description": "Initial desc"}
        ):
            community, _ = service.create_community(
                CommunityForm(),
                creator=curator,
                logo_file=_image_upload("first.png"),
            )
        original_logo = community.logo

        # Non-curator edit must be rejected with PermissionError.
        with test_app.test_request_context(
            f"/community/{community.id}/edit",
            method="POST",
            data={"name": "Hijacked", "description": "Nope"},
        ):
            with pytest.raises(PermissionError):
                service.update_community(community, CommunityForm(), editor=outsider)

        # Curator edit without uploading a new logo preserves the existing logo.
        with test_app.test_request_context(
            f"/community/{community.id}/edit",
            method="POST",
            data={"name": "Updated", "description": "Updated desc"},
        ):
            updated, errors = service.update_community(community, CommunityForm(obj=community), editor=curator)

        assert errors is None
        assert updated.name == "Updated"
        assert updated.description == "Updated desc"
        assert updated.logo == original_logo
        assert os.path.isfile(os.path.join(service.logos_directory(), original_logo))

        # Curator edit with a new logo replaces the file on disk.
        with test_app.test_request_context(
            f"/community/{community.id}/edit",
            method="POST",
            data={"name": "Updated", "description": "New logo desc"},
        ):
            replaced, errors = service.update_community(
                community,
                CommunityForm(obj=community),
                editor=curator,
                logo_file=_image_upload("second.svg", b"<svg/>"),
            )

        assert errors is None
        assert replaced.logo != original_logo
        assert replaced.logo.endswith(".svg")
        assert not os.path.exists(os.path.join(service.logos_directory(), original_logo))
        assert os.path.isfile(os.path.join(service.logos_directory(), replaced.logo))


def test_add_dataset_allows_only_dataset_owner_even_against_curator(test_app, clean_database):
    with test_app.app_context():
        curator = _make_user("curator@example.com")
        owner = _make_user("owner@example.com")
        owners_dataset = _make_dataset(owner, "Owner Songs")
        service = CommunityService()

        with test_app.test_request_context(
            "/community/create", method="POST", data={"name": "Pop Hub", "description": "Pop datasets"}
        ):
            community, _ = service.create_community(CommunityForm(), creator=curator)

        # Even the community's creator/curator cannot add another user's dataset.
        with pytest.raises(PermissionError):
            service.add_dataset(community, owners_dataset.id, user=curator)
        assert community.datasets == []

        # Missing dataset raises LookupError.
        with pytest.raises(LookupError):
            service.add_dataset(community, 99999, user=owner)

        # Dataset owner can add their own dataset (and repeating it is idempotent).
        added = service.add_dataset(community, owners_dataset.id, user=owner)
        service.add_dataset(community, owners_dataset.id, user=owner)
        assert added.id == owners_dataset.id
        assert [d.id for d in community.datasets] == [owners_dataset.id]


def test_remove_dataset_and_add_curator_permissions(test_app, clean_database):
    with test_app.app_context():
        curator = _make_user("curator@example.com")
        owner = _make_user("owner@example.com")
        stranger = _make_user("stranger@example.com")
        ds = _make_dataset(owner, "Folk Songs")
        service = CommunityService()

        with test_app.test_request_context(
            "/community/create", method="POST", data={"name": "Folk Hub", "description": "Folk datasets"}
        ):
            community, _ = service.create_community(CommunityForm(), creator=curator)

        service.add_dataset(community, ds.id, user=owner)

        with pytest.raises(PermissionError):
            service.remove_dataset(community, ds.id, user=stranger)
        assert len(community.datasets) == 1

        service.remove_dataset(community, ds.id, user=owner)
        assert community.datasets == []

        with pytest.raises(PermissionError):
            service.add_curator(community, stranger, actor=stranger)

        service.add_curator(community, owner, actor=curator)
        assert community.is_curator(owner) is True


def test_community_seeder_populates_communities_and_links_datasets(test_app, clean_database, monkeypatch, tmp_path):
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))
    with test_app.app_context():
        with pytest.raises(Exception, match="Users not found"):
            CommunitySeeder().run()

        user1 = _make_user("user1@example.com")
        user2 = _make_user("user2@example.com")
        ds1 = _make_dataset(user1, "Seeded DS 1")
        ds2 = _make_dataset(user2, "Seeded DS 2")

        CommunitySeeder().run()

        communities = CommunityService().list_communities()
        assert len(communities) == 2
        by_name = {c.name: c for c in communities}
        assert by_name["University of Seville"].is_curator(user1)
        assert [d.id for d in by_name["University of Seville"].datasets] == [ds1.id]
        assert by_name["DiversoLab Research"].is_curator(user2)
        assert [d.id for d in by_name["DiversoLab Research"].datasets] == [ds2.id]


def test_add_curator_by_email_and_remove_curator(test_app, clean_database):
    with test_app.app_context():
        curator = _make_user("lead@example.com")
        candidate = _make_user("co-curator@example.com")
        outsider = _make_user("outsider@example.com")
        service = CommunityService()

        with test_app.test_request_context(
            "/community/create", method="POST", data={"name": "Curator Test Hub", "description": "Curators"}
        ):
            community, _ = service.create_community(CommunityForm(), creator=curator)

        # Non-curator cannot add or remove curators.
        with pytest.raises(PermissionError):
            service.add_curator_by_email(community, candidate.email, actor=outsider)
        with pytest.raises(PermissionError):
            service.remove_curator(community, curator.id, actor=outsider)

        # Unknown email returns friendly error message.
        added, error_msg = service.add_curator_by_email(community, "missing@example.com", actor=curator)
        assert added is None
        assert "No user found" in error_msg

        # Cannot remove the sole curator.
        removed, remove_err = service.remove_curator(community, curator.id, actor=curator)
        assert removed is False
        assert "at least one curator" in remove_err

        # Valid email lookup is case-insensitive and grants curator status.
        added, error_msg = service.add_curator_by_email(community, "  CO-CURATOR@EXAMPLE.COM  ", actor=curator)
        assert error_msg is None
        assert added.id == candidate.id
        assert community.is_curator(candidate) is True

        # Removing an unknown user ID raises LookupError.
        with pytest.raises(LookupError):
            service.remove_curator(community, 99999, actor=curator)

        # With two curators present, removing one succeeds.
        removed, remove_err = service.remove_curator(community, candidate.id, actor=curator)
        assert removed is True
        assert remove_err is None
        assert community.is_curator(candidate) is False
        assert community.is_curator(curator) is True
