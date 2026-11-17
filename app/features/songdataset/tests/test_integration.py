import pytest
from pathlib import Path
import shutil

from app import db
from app.features.auth.models import User
from app.features.profile.models import UserProfile
from app.features.songdataset.models import SongDataset
from app.features.songdataset.services import SongDatasetService

pytestmark = pytest.mark.integration


def test_song_upload_page_requires_authentication(test_client):
    response = test_client.get("/songdataset/upload")

    assert response.status_code in (302, 401)


def test_song_preview_returns_not_found_for_unknown_dataset(test_client):
    response = test_client.get("/songdataset/999999/preview")

    assert response.status_code == 404


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
        shutil.copy(Path(__file__).parents[1] / "song_examples" / "Spotify_Youtube.csv", source)
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
        fixture = (
            "Url_spotify,Url_youtube,Artist,Track,Album,Album_type,Danceability,Energy,Key,Loudness,"
            "Speechiness,Acousticness,Instrumentalness,Liveness,Valence,Tempo,Duration_ms,Stream,Views,"
            "Likes,Comments,Licensed,official_video,Channel,Title,Description\n"
            "spotify,youtube,Artist,Track,Album,album,0.5,0.6,4,-5,0.1,0.2,0,0.1,0.5,120,200000,"
            "100,200,30,4,True,True,Channel,Title,Description\n"
        )
        csv_path.write_text(fixture)
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
