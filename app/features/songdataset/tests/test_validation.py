from io import StringIO

import pytest

from app.features.songdataset.validation import (
    EXPECTED_COLUMNS,
    SongCSVValidationError,
    validate_song_csv,
)

pytestmark = pytest.mark.unit


def _csv(**overrides):
    values = {
        "Url_spotify": "spotify",
        "Url_youtube": "youtube",
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


def test_rejects_missing_columns():
    csv = _csv().replace(",Description", "")

    with pytest.raises(SongCSVValidationError, match="Missing required columns"):
        validate_song_csv(StringIO(csv))


@pytest.mark.parametrize("column,value", [("Danceability", "1.1"), ("Tempo", "-1"), ("Views", "not-a-number")])
def test_rejects_invalid_numeric_ranges_and_types(column, value):
    with pytest.raises(SongCSVValidationError):
        validate_song_csv(StringIO(_csv(**{column: value})))


def test_rejects_rows_without_artist_or_track():
    with pytest.raises(SongCSVValidationError, match="Artist and Track"):
        validate_song_csv(StringIO(_csv(Artist="")))
