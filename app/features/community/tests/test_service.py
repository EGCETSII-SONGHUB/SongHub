"""Service-level tests for the community feature against a real database."""

import os
from datetime import datetime, timezone
from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from app.features.auth.repositories import UserRepository
from app.features.community.forms import CommunityForm
from app.features.community.models import CommunityDatasetRequest
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


def _make_community(test_app, service, creator, name: str):
    with test_app.test_request_context(
        "/community/create", method="POST", data={"name": name, "description": f"{name} description"}
    ):
        community, _ = service.create_community(CommunityForm(), creator=creator)
    return community


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

        community.datasets.append(ds)
        service.repository.session.commit()

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


def test_propose_dataset_creates_pending_request(test_app, clean_database):
    with test_app.app_context():
        curator = _make_user("curator@example.com")
        owner = _make_user("owner@example.com")
        ds = _make_dataset(owner, "Proposed Songs")
        service = CommunityService()
        community = _make_community(test_app, service, curator, "Proposal Hub")

        req = service.propose_dataset(community, ds.id, user=owner)

        assert req.status == CommunityDatasetRequest.STATUS_PENDING
        assert req.requester_id == owner.id
        assert req.dataset_id == ds.id
        assert req.community_id == community.id
        # Pending requests must NOT show up as community datasets.
        assert community.datasets == []


def test_propose_dataset_rejects_invalid_proposals(test_app, clean_database):
    with test_app.app_context():
        curator = _make_user("curator@example.com")
        owner = _make_user("owner@example.com")
        other = _make_user("other@example.com")
        ds = _make_dataset(owner, "Owner Songs")
        service = CommunityService()
        community = _make_community(test_app, service, curator, "Rules Hub")

        # Dataset that does not exist.
        with pytest.raises(LookupError):
            service.propose_dataset(community, 99999, user=owner)

        # Only the owner can propose their dataset.
        with pytest.raises(PermissionError):
            service.propose_dataset(community, ds.id, user=other)

        # Duplicate pending request.
        service.propose_dataset(community, ds.id, user=owner)
        with pytest.raises(ValueError):
            service.propose_dataset(community, ds.id, user=owner)

        # Dataset already in the community.
        accepted_ds = _make_dataset(owner, "Already In")
        community.datasets.append(accepted_ds)
        service.repository.session.commit()
        with pytest.raises(ValueError):
            service.propose_dataset(community, accepted_ds.id, user=owner)


def test_accept_request_adds_dataset_to_community(test_app, clean_database):
    with test_app.app_context():
        curator = _make_user("curator@example.com")
        owner = _make_user("owner@example.com")
        ds = _make_dataset(owner, "Accepted Songs")
        service = CommunityService()
        community = _make_community(test_app, service, curator, "Accept Hub")
        req = service.propose_dataset(community, ds.id, user=owner)

        service.accept_request(req, curator, comment="  Welcome!  ")

        assert req.status == CommunityDatasetRequest.STATUS_ACCEPTED
        assert req.comment == "Welcome!"
        assert req.resolved_by_id == curator.id
        assert req.resolved_at is not None
        assert [d.id for d in community.datasets] == [ds.id]


def test_reject_request_does_not_add_dataset(test_app, clean_database):
    with test_app.app_context():
        curator = _make_user("curator@example.com")
        owner = _make_user("owner@example.com")
        ds = _make_dataset(owner, "Rejected Songs")
        service = CommunityService()
        community = _make_community(test_app, service, curator, "Reject Hub")
        req = service.propose_dataset(community, ds.id, user=owner)

        service.reject_request(req, curator, comment="Off topic")

        assert req.status == CommunityDatasetRequest.STATUS_REJECTED
        assert req.comment == "Off topic"
        assert community.datasets == []

        # A rejected dataset can be proposed again.
        again = service.propose_dataset(community, ds.id, user=owner)
        assert again.status == CommunityDatasetRequest.STATUS_PENDING


def test_only_curators_can_resolve_requests(test_app, clean_database):
    with test_app.app_context():
        curator = _make_user("curator@example.com")
        owner = _make_user("owner@example.com")
        outsider = _make_user("outsider@example.com")
        ds = _make_dataset(owner, "Guarded Songs")
        service = CommunityService()
        community = _make_community(test_app, service, curator, "Guarded Hub")
        req = service.propose_dataset(community, ds.id, user=owner)

        # Not even the dataset owner (requester) can resolve their own request.
        for user in (outsider, owner):
            with pytest.raises(PermissionError):
                service.accept_request(req, user)
            with pytest.raises(PermissionError):
                service.reject_request(req, user)
            with pytest.raises(PermissionError):
                service.list_pending_requests(community, user)

        assert req.status == CommunityDatasetRequest.STATUS_PENDING
        assert community.datasets == []


def test_request_cannot_be_resolved_twice(test_app, clean_database):
    with test_app.app_context():
        curator = _make_user("curator@example.com")
        owner = _make_user("owner@example.com")
        ds = _make_dataset(owner, "Once Songs")
        service = CommunityService()
        community = _make_community(test_app, service, curator, "Once Hub")
        req = service.propose_dataset(community, ds.id, user=owner)

        service.reject_request(req, curator)
        with pytest.raises(ValueError):
            service.accept_request(req, curator)
        assert community.datasets == []


def test_list_pending_and_user_requests(test_app, clean_database):
    with test_app.app_context():
        curator = _make_user("curator@example.com")
        owner = _make_user("owner@example.com")
        ds1 = _make_dataset(owner, "First")
        ds2 = _make_dataset(owner, "Second")
        service = CommunityService()
        community = _make_community(test_app, service, curator, "List Hub")
        req1 = service.propose_dataset(community, ds1.id, user=owner)
        req2 = service.propose_dataset(community, ds2.id, user=owner)

        service.accept_request(req1, curator)

        pending = service.list_pending_requests(community, curator)
        assert [r.id for r in pending] == [req2.id]

        # The author sees all their requests with their status.
        mine = service.list_user_requests(owner)
        assert {r.id: r.status for r in mine} == {
            req1.id: CommunityDatasetRequest.STATUS_ACCEPTED,
            req2.id: CommunityDatasetRequest.STATUS_PENDING,
        }
