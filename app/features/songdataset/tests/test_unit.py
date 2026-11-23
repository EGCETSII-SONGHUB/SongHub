from io import StringIO
from types import SimpleNamespace

import pytest

from app.features.songdataset.models import SongDataset, SongFile
from app.features.songdataset.validation import (
    EXPECTED_COLUMNS,
    SongCSVValidationError,
    validate_song_csv,
)

pytestmark = pytest.mark.unit


def _csv(**overrides):
    values = {
        "Url_spotify": "https://open.spotify.com/artist/1",
        "Url_youtube": "https://www.youtube.com/watch?v=1",
        "Artist": "Artist",
        "Track": "Track",
        "Album": "Album",
        "Album_type": "album",
        "Danceability": "0.5",
        "Energy": "0.5",
        "Key": "4",
        "Loudness": "-5",
        "Speechiness": "0.1",
        "Acousticness": "0.2",
        "Instrumentalness": "0",
        "Liveness": "0.1",
        "Valence": "0.5",
        "Tempo": "120",
        "Duration_ms": "200000",
        "Stream": "1000",
        "Views": "2000",
        "Likes": "100",
        "Comments": "10",
        "Licensed": "True",
        "official_video": "True",
        "Channel": "Channel",
        "Title": "Title",
        "Description": "Description",
    }
    values.update(overrides)
    return ",".join(EXPECTED_COLUMNS) + "\n" + ",".join(values[column] for column in EXPECTED_COLUMNS) + "\n"


def test_validates_the_26_column_spotify_youtube_schema():
    result = validate_song_csv(StringIO(_csv()))

    assert result.rows == 1
    assert result.columns == EXPECTED_COLUMNS


def test_validates_schema_with_extra_index_and_uri_columns():
    header = ",Uri," + ",".join(EXPECTED_COLUMNS)
    unit_cols = {"Danceability", "Energy", "Valence"}
    non_neg_cols = {
        "Key",
        "Tempo",
        "Duration_ms",
        "Stream",
        "Views",
        "Likes",
        "Comments",
        "Speechiness",
        "Acousticness",
        "Instrumentalness",
        "Liveness",
    }
    row_values = []
    for col in EXPECTED_COLUMNS:
        if col in unit_cols:
            row_values.append("0.5")
        elif col in non_neg_cols:
            row_values.append("1")
        elif col == "Loudness":
            row_values.append("-5")
        elif col in ("Licensed", "official_video"):
            row_values.append("True")
        elif col == "Album_type":
            row_values.append("album")
        else:
            row_values.append(col)
    row = "0,spotify:track:1," + ",".join(row_values)
    result = validate_song_csv(StringIO(f"{header}\n{row}\n"))

    assert result.rows == 1
    assert "Uri" in result.columns


def test_accepts_spotify_key_minus_one():
    result = validate_song_csv(StringIO(_csv(Key="-1")))
    assert result.rows == 1


def test_rejects_empty_or_header_only_csv():
    with pytest.raises(SongCSVValidationError, match="header"):
        validate_song_csv(StringIO(""))

    header_only = ",".join(EXPECTED_COLUMNS) + "\n"
    with pytest.raises(SongCSVValidationError, match="at least one song"):
        validate_song_csv(StringIO(header_only))


def test_rejects_missing_columns():
    csv_text = _csv().replace(",Description", "")

    with pytest.raises(SongCSVValidationError, match="Missing required columns"):
        validate_song_csv(StringIO(csv_text))


def test_rejects_truncated_csv_rows():
    header = ",".join(EXPECTED_COLUMNS)
    truncated_row = "spotify,youtube,Artist,Track"
    with pytest.raises(SongCSVValidationError, match="Malformed CSV row"):
        validate_song_csv(StringIO(f"{header}\n{truncated_row}\n"))


@pytest.mark.parametrize(
    "column,value",
    [
        ("Danceability", "1.1"),
        ("Danceability", "-0.1"),
        ("Energy", "nan"),
        ("Key", "-2"),
        ("Key", "12"),
        ("Loudness", "11"),
        ("Tempo", "-1"),
        ("Views", "not-a-number"),
        ("Stream", "inf"),
    ],
)
def test_rejects_invalid_numeric_ranges_and_types(column, value):
    with pytest.raises(SongCSVValidationError):
        validate_song_csv(StringIO(_csv(**{column: value})))


@pytest.mark.parametrize("column", ["Licensed", "official_video"])
def test_rejects_invalid_boolean_values(column):
    with pytest.raises(SongCSVValidationError, match="must be boolean"):
        validate_song_csv(StringIO(_csv(**{column: "maybe"})))


def test_rejects_invalid_album_type():
    with pytest.raises(SongCSVValidationError, match="Album_type is invalid"):
        validate_song_csv(StringIO(_csv(Album_type="podcast")))


def test_rejects_rows_without_artist_or_track():
    with pytest.raises(SongCSVValidationError, match="Artist and Track"):
        validate_song_csv(StringIO(_csv(Artist="")))
    with pytest.raises(SongCSVValidationError, match="Artist and Track"):
        validate_song_csv(StringIO(_csv(Track="   ")))


def test_song_file_to_dict_matches_hubfile_contract():
    song_file = SongFile(id=9, name="tracks.csv", checksum="abc", size=2048, dataset_id=3)
    payload = song_file.to_dict()

    assert payload == {
        "id": 9,
        "name": "tracks.csv",
        "checksum": "abc",
        "size_in_bytes": 2048,
        "size_in_human_format": "2.0 KB",
        "url": "/songdataset/file/9/download",
    }


def test_song_dataset_aggregates_song_files():
    stub = SimpleNamespace(
        song_files=[SimpleNamespace(size=512), SimpleNamespace(size=1024)],
    )
    assert len(SongDataset.files(stub)) == 2
    assert SongDataset.get_files_count(stub) == 2
    assert SongDataset.get_file_total_size(stub) == 1536
