import csv
import math
from dataclasses import dataclass
from io import TextIOBase
from typing import Iterable


EXPECTED_COLUMNS = (
    "Url_spotify", "Url_youtube", "Artist", "Track", "Album", "Album_type",
    "Danceability", "Energy", "Key", "Loudness", "Speechiness",
    "Acousticness", "Instrumentalness", "Liveness", "Valence", "Tempo",
    "Duration_ms", "Stream", "Views", "Likes", "Comments", "Licensed",
    "official_video", "Channel", "Title", "Description",
)

NUMERIC_COLUMNS = {
    "Danceability": (0, 1),
    "Energy": (0, 1),
    "Key": (0, 11),
    "Loudness": (-60, 10),
    "Speechiness": (0, 1),
    "Acousticness": (0, 1),
    "Instrumentalness": (0, 1),
    "Liveness": (0, 1),
    "Valence": (0, 1),
    "Tempo": (0, None),
    "Duration_ms": (0, None),
    "Stream": (0, None),
    "Views": (0, None),
    "Likes": (0, None),
    "Comments": (0, None),
}


@dataclass(frozen=True)
class SongValidationResult:
    rows: int
    columns: tuple[str, ...]


class SongCSVValidationError(ValueError):
    """Raised when a song CSV does not match the SongHub contract."""


def _number(value: str, column: str, row: int) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise SongCSVValidationError(f"{column} must be numeric at row {row}") from exc
    if not math.isfinite(parsed):
        raise SongCSVValidationError(f"{column} must be finite at row {row}")
    lower, upper = NUMERIC_COLUMNS[column]
    if (lower is not None and parsed < lower) or (upper is not None and parsed > upper):
        raise SongCSVValidationError(f"{column} is outside its valid range at row {row}")
    return parsed


def validate_song_csv(source: TextIOBase | Iterable[str]) -> SongValidationResult:
    """Validate headers, row types and metric ranges without loading a dataset in memory."""

    reader = csv.DictReader(source)
    if not reader.fieldnames:
        raise SongCSVValidationError("CSV file must contain a header")
    columns = tuple(reader.fieldnames)
    missing = [column for column in EXPECTED_COLUMNS if column not in columns]
    if missing:
        raise SongCSVValidationError(f"Missing required columns: {', '.join(missing)}")
    rows = 0
    for row_number, row in enumerate(reader, start=2):
        for column in NUMERIC_COLUMNS:
            value = row.get(column, "").strip()
            if value:
                _number(value, column, row_number)
        if not row.get("Artist", "").strip() or not row.get("Track", "").strip():
            raise SongCSVValidationError(f"Artist and Track are required at row {row_number}")
        rows += 1
    if rows == 0:
        raise SongCSVValidationError("CSV file must contain at least one song")
    return SongValidationResult(rows=rows, columns=columns)
