import io
import shutil
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from app import db
from app.features.auth.models import User
from app.features.profile.models import UserProfile
from app.features.songdataset.models import SongDataset
from app.features.songdataset.services import SongDatasetService
from app.features.songdataset.validation import EXPECTED_COLUMNS

pytestmark = pytest.mark.integration

VALID_HEADER = ",".join(EXPECTED_COLUMNS)
ROCK_ROW = (
    "spotify,youtube,Gorillaz,Feel Good Inc.,Demon Days,album,0.818,0.705,6,-6.679,0.177,0.008,0.002,0.613,0.772,"
    "138.559,222640,1040234854,693555221,6220896,169907,True,True,Gorillaz,Gorillaz - Feel Good Inc.,Official video"
)
POP_ROW = (
    "spotify,youtube,Coldplay,Yellow,Parachutes,album,0.429,0.661,11,-7.227,0.028,0.002,0.0001,0.234,0.285,"
    "173.372,266773,1500000000,850000000,4000000,120000,True,True,Coldplay,Coldplay - Yellow,Official video"
)


def _csv_bytes(*rows):
    return (VALID_HEADER + "\n" + "\n".join(rows) + "\n").encode("utf-8")


def _signup_and_login(test_client, email="songowner@example.com", password="ownerpass"):
    resp = test_client.post(
        "/signup/",
        data={"email": email, "password": password, "name": "Song", "surname": "Owner"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    with test_client.application.app_context():
        return User.query.filter_by(email=email).first().id


def test_song_upload_page_requires_authentication(test_client):
    response = test_client.get("/songdataset/upload")

    assert response.status_code in (302, 401)


def test_song_upload_page_renders_for_authenticated_user(test_client):
    _signup_and_login(test_client)
    response = test_client.get("/songdataset/upload")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "songUploadDropzone" in html
    assert 'accept=".csv,text/csv"' in html


def test_song_preview_returns_not_found_for_unknown_dataset(test_client):
    response = test_client.get("/songdataset/999999/preview")

    assert response.status_code == 404


def test_temp_csv_upload_validation_and_deletion_endpoints(test_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))
    _signup_and_login(test_client)

    bad_ext = test_client.post(
        "/songdataset/file/upload",
        data={"file": (io.BytesIO(b"hello"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert bad_ext.status_code == 400

    bad_schema = test_client.post(
        "/songdataset/file/upload",
        data={"file": (io.BytesIO(b"Artist,Track\nGorillaz,Feel Good Inc.\n"), "bad.csv")},
        content_type="multipart/form-data",
    )
    assert bad_schema.status_code == 400
    assert "Missing required columns" in bad_schema.get_json()["message"]

    good = test_client.post(
        "/songdataset/file/upload",
        data={"file": (io.BytesIO(_csv_bytes(ROCK_ROW)), "good.csv")},
        content_type="multipart/form-data",
    )
    assert good.status_code == 200
    payload = good.get_json()
    assert payload["filename"] == "good.csv"
    assert payload["rows"] == 1

    deleted = test_client.post("/songdataset/file/delete", json={"file": "good.csv"})
    assert deleted.status_code == 200
    assert test_client.post("/songdataset/file/delete", json={"file": "good.csv"}).status_code == 404


def test_end_to_end_http_upload_edit_preview_download_api_and_explore(test_client, test_app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))
    owner_id = _signup_and_login(test_client, "artist@example.com")

    # Reject missing required metadata
    invalid = test_client.post("/songdataset/upload", data={"title": "", "description": ""})
    assert invalid.status_code == 400

    # Upload via /songdataset/upload with mocked Zenodo sync returning DOI
    with patch("app.features.zenodo.services.ZenodoService.synchronize_dataset") as sync_mock:

        def _fake_sync(dataset):
            dataset.ds_meta_data.deposition_id = 500
            dataset.ds_meta_data.dataset_doi = "10.1234/song-http"
            db.session.commit()
            return {"status": "synchronized", "deposition_id": 500, "doi": "10.1234/song-http"}

        sync_mock.side_effect = _fake_sync
        created = test_client.post(
            "/songdataset/upload",
            data={
                "title": "Rock Classics",
                "description": "Rock tracks dataset",
                "publication_type": "none",
                "tags": "spotify, rock",
                "authors-0-name": "Guest, Alice",
                "authors-0-affiliation": "Music Lab",
                "file": (io.BytesIO(_csv_bytes(ROCK_ROW, POP_ROW)), "rock.csv"),
            },
            content_type="multipart/form-data",
        )
    assert created.status_code == 201
    dataset_id = created.get_json()["dataset_id"]

    # Detail page renders Song statistics and file download
    detail = test_client.get("/doi/10.1234/song-http/")
    detail_html = detail.get_data(as_text=True)
    assert detail.status_code == 200
    assert "Rock Classics" in detail_html
    assert "Song statistics" in detail_html
    assert "Guest, Alice" in detail_html

    # Preview endpoint supports pagination and track/artist filtering
    preview = test_client.get(f"/songdataset/{dataset_id}/preview?limit=1&offset=0&q=Coldplay")
    assert preview.status_code == 200
    preview_json = preview.get_json()
    assert preview_json["total"] == 1
    assert preview_json["rows"][0]["Track"] == "Yellow"
    assert preview_json["summary"]["number_of_songs"] == 2

    # Edit page GET + POST
    edit_page = test_client.get(f"/songdataset/{dataset_id}/edit")
    assert edit_page.status_code == 200
    assert "Rock Classics" in edit_page.get_data(as_text=True)

    bad_edit = test_client.post(f"/songdataset/{dataset_id}/edit", data={"title": "", "description": "Valid"})
    assert bad_edit.status_code == 400

    good_edit = test_client.post(
        f"/songdataset/{dataset_id}/edit",
        data={
            "title": "Rock Classics Updated",
            "description": "Updated description",
            "tags": "rock, updated",
            "file": (io.BytesIO(_csv_bytes(ROCK_ROW)), "rock_only.csv"),
        },
        content_type="multipart/form-data",
    )
    assert good_edit.status_code == 200

    # File download and full dataset ZIP download
    with test_app.app_context():
        stored = db.session.get(SongDataset, dataset_id)
        file_id = stored.song_files[0].id
        assert stored.song_metrics.number_of_songs == 1
        assert stored.ds_meta_data.user_id if hasattr(stored.ds_meta_data, "user_id") else stored.user_id == owner_id

    csv_dl = test_client.get(f"/songdataset/file/{file_id}/download")
    assert csv_dl.status_code == 200
    assert b"Feel Good Inc." in csv_dl.data

    zip_dl = test_client.get(f"/dataset/download/{dataset_id}")
    assert zip_dl.status_code == 200
    with ZipFile(io.BytesIO(zip_dl.data)) as archive:
        assert any(name.endswith("rock_only.csv") for name in archive.namelist())

    # REST API includes SongDataset polymorphically
    api_list = test_client.get("/api/v1/datasets/")
    assert api_list.status_code == 200
    assert any(item["name"] == "Rock Classics Updated" for item in api_list.get_json()["items"])

    # Explore searches inside CSV (for both dataset_type="any" and "song") and by title, excluding when "uvl"
    assert len(test_client.post("/explore", json={"query": "Gorillaz"}).get_json()) == 1
    assert len(test_client.post("/explore", json={"query": "Gorillaz", "dataset_type": "song"}).get_json()) == 1
    assert len(test_client.post("/explore", json={"query": "Rock Classics Updated"}).get_json()) == 1
    assert test_client.post("/explore", json={"query": "Gorillaz", "dataset_type": "uvl"}).get_json() == []


def test_draft_song_dataset_and_edit_are_hidden_from_strangers(test_client, test_app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))
    _signup_and_login(test_client, "owner2@example.com")

    with patch("app.features.zenodo.services.ZenodoService.synchronize_dataset", side_effect=RuntimeError("offline")):
        resp = test_client.post(
            "/dataset/upload",
            data={
                "title": "Local Draft Song",
                "desc": "Unsynchronized draft",
                "publication_type": "none",
                "song_filename": _stage_temp_csv(test_client, "draft.csv"),
            },
        )
    assert resp.status_code == 201
    with test_app.app_context():
        draft = SongDataset.query.first()
        draft_id = draft.id
        file_id = draft.song_files[0].id

    test_client.get("/logout")
    _signup_and_login(test_client, "stranger@example.com")

    assert test_client.get(f"/songdataset/{draft_id}/preview").status_code == 404
    assert test_client.get(f"/songdataset/file/{file_id}/download").status_code == 404
    assert test_client.get(f"/songdataset/{draft_id}/edit").status_code == 404
    assert (
        test_client.post(f"/songdataset/{draft_id}/edit", data={"title": "Hacked", "description": "x"}).status_code
        == 404
    )


def _stage_temp_csv(test_client, name):
    upload = test_client.post(
        "/dataset/file/upload",
        data={"file": (io.BytesIO(_csv_bytes(ROCK_ROW)), name)},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 200
    return upload.get_json()["filename"]


def test_song_search_matches_rows_in_csv(test_app, clean_database, tmp_path, monkeypatch):
    with test_app.app_context():
        user = User(email="search@example.com", password="1234")
        user.profile = UserProfile(name="Search", surname="Owner", affiliation="SongHub")
        db.session.add(user)
        db.session.commit()
        monkeypatch.setenv("WORKING_DIR", str(tmp_path))
        temp = tmp_path / "temp"
        temp.mkdir()
        source = temp / "songs.csv"
        shutil.copy(Path(__file__).parents[1] / "song_examples" / "spotify_youtube_rock_alt.csv", source)
        monkeypatch.setattr(user, "temp_folder", lambda: str(temp))
        dataset = SongDatasetService().create_from_upload(
            {"title": "Full songs", "description": "Complete CSV", "publication_type": "none"},
            source.name,
            user,
        )
        assert dataset.contains_query("Gorillaz Feel Good Inc.", str(tmp_path))
        assert not dataset.contains_query("artist-that-does-not-exist", str(tmp_path))


def test_song_service_persists_metadata_metrics_and_file(test_app, clean_database, tmp_path, monkeypatch):
    with test_app.app_context():
        user = User(email="songs@example.com", password="password")
        user.profile = UserProfile(name="Song", surname="Owner", affiliation="SongHub")
        db.session.add(user)
        db.session.commit()
        monkeypatch.setenv("WORKING_DIR", str(tmp_path))
        temp = tmp_path / "temp"
        temp.mkdir()
        csv_path = temp / "songs.csv"
        csv_path.write_bytes(_csv_bytes(ROCK_ROW))
        monkeypatch.setattr(user, "temp_folder", lambda: str(temp))

        dataset = SongDatasetService().create_from_upload(
            {"title": "Songs", "description": "A song dataset", "publication_type": "none"},
            "songs.csv",
            user,
        )

        stored = db.session.get(SongDataset, dataset.id)
        assert stored.song_metrics.number_of_songs == 1
        assert stored.song_metrics.number_of_artists == 1
        assert stored.song_files[0].name == "songs.csv"
