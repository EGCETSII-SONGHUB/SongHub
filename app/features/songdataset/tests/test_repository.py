import json

import pytest
import sqlalchemy as sa

from app import db
from app.features.auth.models import User
from app.features.dataset.models import BaseDataset, DSMetaData, PublicationType, UVLDataset
from app.features.dataset.repositories import DataSetRepository
from app.features.songdataset.models import SongDataset, SongFile, SongMetadata, SongMetrics
from app.features.songdataset.repositories import SongDatasetRepository

pytestmark = pytest.mark.repository


def _make_user(email="repo@example.com"):
    user = User(email=email, password="secret")
    db.session.add(user)
    db.session.flush()
    return user


def _make_song_dataset(user, title="Repo Songs", doi=None):
    ds_meta = DSMetaData(
        title=title,
        description=f"Desc for {title}",
        publication_type=PublicationType.NONE,
        dataset_doi=doi,
    )
    metrics = SongMetrics(number_of_songs=10, number_of_artists=3, average_streams=5000.0)
    song_meta = SongMetadata(csv_filename="tracks.csv", columns=json.dumps(["Artist", "Track"]), song_metrics=metrics)
    dataset = SongDataset(user_id=user.id, dataset_type="song", ds_meta_data=ds_meta, song_metadata=song_meta)
    dataset.song_files.append(SongFile(name="tracks.csv", checksum="deadbeef", size=128))
    db.session.add(dataset)
    db.session.commit()
    return dataset


def test_song_dataset_repository_persists_and_scopes_to_owner(test_app, clean_database):
    with test_app.app_context():
        owner = _make_user("owner@example.com")
        stranger = _make_user("stranger@example.com")
        dataset = _make_song_dataset(owner, doi="10.1234/repo-song")

        repo = SongDatasetRepository()
        assert repo.get_by_id(dataset.id) is not None
        assert repo.get_for_owner(dataset.id, owner.id).id == dataset.id
        assert repo.get_for_owner(dataset.id, stranger.id) is None


def test_dataset_repository_coexists_polymorphically_with_uvl_and_song(test_app, clean_database):
    with test_app.app_context():
        owner = _make_user("poly@example.com")
        song = _make_song_dataset(owner, title="Song Set", doi="10.1234/song-poly")
        uvl_meta = DSMetaData(
            title="UVL Set",
            description="UVL description",
            publication_type=PublicationType.DATA_MANAGEMENT_PLAN,
            dataset_doi="10.1234/uvl-poly",
        )
        db.session.add(uvl_meta)
        db.session.flush()
        uvl = UVLDataset(user_id=owner.id, ds_meta_data_id=uvl_meta.id)
        db.session.add(uvl)
        db.session.commit()

        repo = DataSetRepository()
        assert repo.count_synchronized_datasets() == 2
        items = repo.get_synchronized(owner.id)
        assert {type(item) for item in items} == {SongDataset, UVLDataset}
        assert all(isinstance(item, BaseDataset) for item in items)
        assert {item.id for item in items} == {song.id, uvl.id}


def test_orm_delete_and_orphan_removal_cascade_cleanly(test_app, clean_database):
    with test_app.app_context():
        owner = _make_user("orm-cascade@example.com")
        dataset = _make_song_dataset(owner, title="Cascade ORM")
        extra_file = SongFile(name="extra.csv", checksum="cafebabe", size=64)
        dataset.song_files.append(extra_file)
        db.session.commit()

        extra_id = extra_file.id
        dataset.song_files.remove(extra_file)
        db.session.commit()
        assert db.session.get(SongFile, extra_id) is None

        dataset_id = dataset.id
        file_id = dataset.song_files[0].id
        meta_id = dataset.song_metadata_id
        metrics_id = dataset.song_metadata.song_metrics_id

        dataset.delete()

        assert db.session.get(SongDataset, dataset_id) is None
        assert db.session.get(BaseDataset, dataset_id) is None
        assert db.session.get(SongFile, file_id) is None
        assert db.session.get(SongMetadata, meta_id) is None
        assert db.session.get(SongMetrics, metrics_id) is None


def test_sql_delete_on_data_set_cascades_to_song_dataset_and_files(test_app, clean_database):
    with test_app.app_context():
        owner = _make_user("sql-cascade@example.com")
        dataset = _make_song_dataset(owner, title="Cascade SQL")
        dataset_id = dataset.id
        file_id = dataset.song_files[0].id

        db.session.execute(sa.text("DELETE FROM data_set WHERE id = :id"), {"id": dataset_id})
        db.session.commit()
        db.session.expire_all()

        assert db.session.get(BaseDataset, dataset_id) is None
        assert db.session.get(SongDataset, dataset_id) is None
        assert db.session.get(SongFile, file_id) is None
