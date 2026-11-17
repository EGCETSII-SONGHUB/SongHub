"""Repository-level tests for the community feature against the database."""

from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.features.auth.repositories import UserRepository
from app.features.community.repositories import CommunityRepository
from app.features.dataset.models import PublicationType
from app.features.dataset.repositories import DataSetRepository, DSMetaDataRepository

pytestmark = pytest.mark.repository


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


def test_create_and_get_by_name(test_app, clean_database):
    with test_app.app_context():
        user = _make_user("repo-creator@example.com")
        repo = CommunityRepository()
        created = repo.create(
            name="Audio MIR",
            description="Music information retrieval datasets",
            logo=None,
            creator_id=user.id,
        )

        found = repo.get_by_name("Audio MIR")
        assert found is not None
        assert found.id == created.id
        assert found.creator_id == user.id
        assert repo.get_by_name("Nonexistent") is None


def test_get_all_ordered_returns_newest_first(test_app, clean_database):
    with test_app.app_context():
        user = _make_user("repo-order@example.com")
        repo = CommunityRepository()
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        oldest = repo.create(name="Oldest", description="First", creator_id=user.id, created_at=base)
        newest = repo.create(
            name="Newest",
            description="Second",
            creator_id=user.id,
            created_at=base + timedelta(days=1),
        )

        ordered = repo.get_all_ordered()
        assert [c.id for c in ordered] == [newest.id, oldest.id]


def test_get_by_curator_and_dataset_associations(test_app, clean_database):
    with test_app.app_context():
        curator = _make_user("curator@example.com")
        other = _make_user("other@example.com")
        dataset = _make_dataset(other, "Rock Tracks")

        repo = CommunityRepository()
        curated = repo.create(name="Curated", description="Desc", creator_id=curator.id)
        curated.curators.append(curator)
        curated.datasets.append(dataset)

        not_curated = repo.create(name="Other", description="Desc", creator_id=other.id)
        not_curated.curators.append(other)
        db.session.commit()

        found = repo.get_by_curator(curator.id)
        assert [c.id for c in found] == [curated.id]
        assert [d.id for d in found[0].datasets] == [dataset.id]
