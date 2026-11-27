import os
from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from app import db
from app.features.auth.models import User
from app.features.profile.models import UserProfile
from app.features.songdataset.models import SongDataset
from app.features.songdataset.services import SongDatasetService
from app.features.songdataset.validation import EXPECTED_COLUMNS, SongCSVValidationError

pytestmark = pytest.mark.service

VALID_HEADER = ",".join(EXPECTED_COLUMNS)
VALID_ROW_1 = (
    "spotify,youtube,Gorillaz,Feel Good Inc.,Demon Days,album,0.8,0.7,6,-6.5,0.1,0.01,0.002,0.6,0.7,138,222640,"
    "10000,20000,500,20,True,True,Gorillaz,Feel Good Inc.,Official video"
)
VALID_ROW_2 = (
    "spotify,youtube,Radiohead,Creep,Pablo Honey,album,0.5,0.4,7,-9.0,0.05,0.02,0.0,0.1,0.3,92,238000,"
    "30000,40000,900,40,True,True,Radiohead,Creep,Live"
)


def _csv_bytes(rows=(VALID_ROW_1,)):
    return (VALID_HEADER + "\n" + "\n".join(rows) + "\n").encode("utf-8")


def _csv_upload(filename="songs.csv", content=None):
    return FileStorage(stream=BytesIO(content if content is not None else _csv_bytes()), filename=filename)


def _user(email="service@example.com", with_profile=True):
    user = User(email=email, password="secret")
    if with_profile:
        user.profile = UserProfile(name="Ada", surname="Lovelace", affiliation="SongHub", orcid="0000-0001-0002-0003")
    db.session.add(user)
    db.session.commit()
    return user


def test_save_and_delete_temp_csv(test_app, clean_database, tmp_path, monkeypatch):
    with test_app.app_context():
        user = _user()
        temp_dir = tmp_path / "temp"
        monkeypatch.setattr(user, "temp_folder", lambda: str(temp_dir))
        service = SongDatasetService()

        bad_ext = service.save_temp_csv(_csv_upload("notes.txt"), user)
        assert bad_ext["code"] == 400

        corrupt = service.save_temp_csv(_csv_upload("bad.csv", b"\xff\xfe\x00\x00"), user)
        assert corrupt["code"] == 400
        assert not (temp_dir / "bad.csv").exists()

        saved = service.save_temp_csv(_csv_upload("valid.csv", _csv_bytes((VALID_ROW_1, VALID_ROW_2))), user)
        assert saved["code"] == 200
        assert saved["filename"] == "valid.csv"
        assert saved["rows"] == 2
        assert saved["summary"]["number_of_artists"] == 2

        deleted = service.delete_temp_csv("valid.csv", user)
        assert deleted["code"] == 200
        assert service.delete_temp_csv("valid.csv", user)["code"] == 404
        assert service.delete_temp_csv("", user)["code"] == 400


def test_create_from_upload_without_profile_and_with_extra_authors(test_app, clean_database, tmp_path, monkeypatch):
    with test_app.app_context():
        user = _user(email="noprofile@example.com", with_profile=False)
        monkeypatch.setenv("WORKING_DIR", str(tmp_path))
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        (temp_dir / "songs.csv").write_bytes(_csv_bytes((VALID_ROW_1, VALID_ROW_2)))
        monkeypatch.setattr(user, "temp_folder", lambda: str(temp_dir))

        service = SongDatasetService()
        dataset = service.create_from_upload(
            {"title": "My Songs", "description": "Two tracks", "publication_type": "none", "tags": "rock, alt"},
            "songs.csv",
            user,
            extra_authors=[{"name": "Collaborator, Bob", "affiliation": "Lab"}],
        )

        stored = db.session.get(SongDataset, dataset.id)
        assert stored.song_metrics.number_of_songs == 2
        assert stored.song_metrics.number_of_artists == 2
        assert stored.song_metrics.average_streams == 20000.0
        assert [a.name for a in stored.ds_meta_data.authors] == ["noprofile@example.com", "Collaborator, Bob"]
        assert not (temp_dir / "songs.csv").exists()
        assert os.path.isfile(stored.file_path(str(tmp_path)))


def test_update_metadata_and_replace_file_with_rollback(test_app, clean_database, tmp_path, monkeypatch):
    with test_app.app_context():
        user = _user("edit@example.com")
        monkeypatch.setenv("WORKING_DIR", str(tmp_path))
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        (temp_dir / "initial.csv").write_bytes(_csv_bytes((VALID_ROW_1,)))
        monkeypatch.setattr(user, "temp_folder", lambda: str(temp_dir))

        service = SongDatasetService()
        dataset = service.create_from_upload(
            {"title": "Original", "description": "Original desc", "publication_type": "none"},
            "initial.csv",
            user,
        )

        with pytest.raises(ValueError, match="title and description"):
            service.update_metadata(dataset, {"title": "", "description": "Valid"})

        service.update_metadata(
            dataset,
            {"title": "Updated", "description": "Updated desc", "tags": "pop", "publication_type": "article"},
        )
        assert dataset.ds_meta_data.title == "Updated"
        assert dataset.ds_meta_data.publication_type.value == "article"

        with pytest.raises(SongCSVValidationError):
            service.replace_file(dataset, _csv_upload("bad.csv", b"Artist,Track\nA,B\n"))
        db.session.refresh(dataset)
        assert dataset.song_metadata.csv_filename == "initial.csv"

        service.replace_file(dataset, _csv_upload("updated.csv", _csv_bytes((VALID_ROW_1, VALID_ROW_2))))
        assert dataset.song_metadata.csv_filename == "updated.csv"
        assert dataset.song_metrics.number_of_songs == 2
        assert dataset.song_files[0].name == "updated.csv"


def test_contains_query_and_preview_with_relative_working_dir(test_app, clean_database, tmp_path, monkeypatch):
    with test_app.app_context():
        user = _user("preview@example.com")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("WORKING_DIR", "")
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        (temp_dir / "mix.csv").write_bytes(_csv_bytes((VALID_ROW_1, VALID_ROW_2)))
        monkeypatch.setattr(user, "temp_folder", lambda: str(temp_dir))

        service = SongDatasetService()
        dataset = service.create_from_upload(
            {"title": "Mix", "description": "Preview test", "publication_type": "none"},
            "mix.csv",
            user,
        )

        assert dataset.contains_query("Gorillaz Feel Good Inc.")
        assert not dataset.contains_query("Unknown Artist")
        assert not service.contains_query(str(tmp_path / "missing.csv"), "Gorillaz")

        preview = service.get_dataset_preview(dataset, limit=1, offset=0, query="Radiohead")
        assert preview["total"] == 1
        assert preview["rows"][0]["Track"] == "Creep"
        assert preview["summary"]["number_of_songs"] == 2
