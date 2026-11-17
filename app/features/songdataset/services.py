import csv
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from splent_framework.services.BaseService import BaseService

from app import db
from app.features.dataset.models import Author, DSMetaData, PublicationType
from app.features.songdataset.models import SongDataset, SongFile, SongMetadata, SongMetrics
from app.features.songdataset.repositories import (
    SongDatasetRepository,
    SongFileRepository,
    SongMetadataRepository,
    SongMetricsRepository,
)
from app.features.songdataset.validation import SongCSVValidationError, validate_song_csv


class SongDatasetService(BaseService):
    def __init__(self):
        super().__init__(SongDatasetRepository())
        self.metadata_repository = SongMetadataRepository()
        self.metrics_repository = SongMetricsRepository()
        self.file_repository = SongFileRepository()

    def get_for_owner(self, dataset_id: int, user_id: int) -> SongDataset | None:
        return self.repository.get_for_owner(dataset_id, user_id)

    def validate_file(self, file_path: str):
        if Path(file_path).suffix.lower() != ".csv":
            raise SongCSVValidationError("Song datasets must be CSV files")
        try:
            with open(file_path, "r", encoding="utf-8-sig", newline="") as stream:
                return validate_song_csv(stream)
        except (UnicodeDecodeError, csv.Error) as exc:
            raise SongCSVValidationError(f"Invalid CSV format: {exc}") from exc

    def save_temp_csv(self, file, current_user) -> dict:
        if not file or not file.filename or not file.filename.lower().endswith(".csv"):
            return {"status": "error", "code": 400, "message": "No valid CSV file"}
        folder = current_user.temp_folder()
        os.makedirs(folder, exist_ok=True)
        safe_name = os.path.basename(file.filename)
        if not safe_name:
            return {"status": "error", "code": 400, "message": "No valid CSV file"}
        target = os.path.join(folder, safe_name)
        try:
            file.save(target)
            result = self.validate_file(target)
            summary = self.summarize_file(target)
        except (OSError, SongCSVValidationError, UnicodeDecodeError, csv.Error) as exc:
            if os.path.exists(target):
                os.remove(target)
            return {"status": "error", "code": 400, "message": str(exc)}
        return {
            "status": "ok",
            "code": 200,
            "message": "Song CSV uploaded and validated successfully",
            "filename": safe_name,
            "rows": result.rows,
            "summary": summary,
        }

    def delete_temp_csv(self, filename: str, current_user) -> dict:
        safe_name = os.path.basename((filename or "").strip())
        if not safe_name:
            return {"status": "error", "code": 400, "error": "Error: filename missing"}
        target = os.path.join(current_user.temp_folder(), safe_name)
        if not os.path.isfile(target):
            return {"status": "error", "code": 404, "error": "Error: File not found"}
        os.remove(target)
        return {"status": "ok", "code": 200, "message": "File deleted successfully"}

    def create_from_upload(
        self,
        form_data: dict,
        filename: str,
        current_user,
        extra_authors: list[dict] | None = None,
    ) -> SongDataset:
        title = (form_data.get("title") or "").strip()
        description = (form_data.get("description") or "").strip()
        if not title or not description:
            raise ValueError("title and description are required")

        safe_name = os.path.basename((filename or "").strip())
        if not safe_name:
            raise SongCSVValidationError("A valid CSV filename is required")
        source = os.path.join(current_user.temp_folder(), safe_name)
        if not os.path.isfile(source):
            raise FileNotFoundError(f"Uploaded CSV '{safe_name}' was not found in temporary storage")

        validation = self.validate_file(source)
        summary = self.summarize_file(source)
        metrics = SongMetrics(
            number_of_songs=summary["number_of_songs"],
            number_of_artists=summary["number_of_artists"],
            average_streams=summary["average_stream"],
            average_views=summary["average_views"],
            average_likes=summary["average_likes"],
        )
        metadata = SongMetadata(
            csv_filename=safe_name,
            columns=json.dumps(validation.columns),
            song_metrics=metrics,
        )
        dataset_meta = self._dataset_metadata(
            {
                "title": title,
                "description": description,
                "publication_type": form_data.get("publication_type", "none"),
                "publication_doi": form_data.get("publication_doi"),
                "dataset_doi": form_data.get("dataset_doi"),
                "tags": form_data.get("tags"),
            }
        )
        if getattr(current_user, "profile", None) is not None:
            main_author = Author(
                name=f"{current_user.profile.surname}, {current_user.profile.name}",
                affiliation=current_user.profile.affiliation,
                orcid=current_user.profile.orcid,
            )
        else:
            main_author = Author(name=current_user.email)
        dataset_meta.authors.append(main_author)

        for author_data in extra_authors or []:
            name = (author_data.get("name") or "").strip()
            if name:
                dataset_meta.authors.append(
                    Author(
                        name=name,
                        affiliation=(author_data.get("affiliation") or "").strip() or None,
                        orcid=(author_data.get("orcid") or "").strip() or None,
                    )
                )

        with open(source, "rb") as stream:
            checksum = hashlib.md5(stream.read()).hexdigest()

        dataset = SongDataset(
            user_id=current_user.id,
            dataset_type="song",
            ds_meta_data=dataset_meta,
            song_metadata=metadata,
        )
        dataset.song_files.append(SongFile(name=safe_name, checksum=checksum, size=os.path.getsize(source)))

        try:
            db.session.add(dataset)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        destination = os.path.join(
            os.getenv("WORKING_DIR", ""),
            "uploads",
            f"user_{current_user.id}",
            f"dataset_{dataset.id}",
        )
        os.makedirs(destination, exist_ok=True)
        shutil.copy2(source, os.path.join(destination, safe_name))
        if os.path.exists(source):
            os.remove(source)
        return dataset

    def update_metadata(self, dataset: SongDataset, form_data: dict) -> SongDataset:
        title = (form_data.get("title") or "").strip()
        description = (form_data.get("description") or "").strip()
        if not title or not description:
            raise ValueError("title and description are required")

        try:
            dataset.ds_meta_data.title = title
            dataset.ds_meta_data.description = description
            if "tags" in form_data:
                dataset.ds_meta_data.tags = (form_data.get("tags") or "").strip() or None
            if "publication_type" in form_data and form_data.get("publication_type"):
                dataset.ds_meta_data.publication_type = self._parse_publication_type(form_data.get("publication_type"))
            if "publication_doi" in form_data:
                dataset.ds_meta_data.publication_doi = (form_data.get("publication_doi") or "").strip() or None
            db.session.commit()
            return dataset
        except Exception:
            db.session.rollback()
            raise

    def replace_file(self, dataset: SongDataset, uploaded_file) -> SongDataset:
        """Replace the CSV and atomically refresh validation, metrics and checksum."""

        if not uploaded_file or not uploaded_file.filename or not uploaded_file.filename.lower().endswith(".csv"):
            raise SongCSVValidationError("Song datasets must be CSV files")
        new_name = os.path.basename(uploaded_file.filename)
        if not new_name:
            raise SongCSVValidationError("Song datasets must be CSV files")

        with tempfile.TemporaryDirectory() as temp_folder:
            temporary_path = os.path.join(temp_folder, new_name)
            uploaded_file.save(temporary_path)
            try:
                validation = self.validate_file(temporary_path)
                summary = self.summarize_file(temporary_path)
                with open(temporary_path, "rb") as stream:
                    checksum = hashlib.md5(stream.read()).hexdigest()
                destination = os.path.join(
                    os.getenv("WORKING_DIR", ""),
                    "uploads",
                    f"user_{dataset.user_id}",
                    f"dataset_{dataset.id}",
                )
                os.makedirs(destination, exist_ok=True)
                old_path = os.path.join(destination, dataset.song_metadata.csv_filename)
                new_path = os.path.join(destination, new_name)
                shutil.copy2(temporary_path, new_path)
                if old_path != new_path and os.path.exists(old_path):
                    os.remove(old_path)
                old_file = dataset.song_files[0] if dataset.song_files else None
                if old_file is None:
                    old_file = SongFile(dataset_id=dataset.id)
                    dataset.song_files.append(old_file)
                old_file.name = new_name
                old_file.checksum = checksum
                old_file.size = os.path.getsize(temporary_path)
                dataset.song_metadata.csv_filename = new_name
                dataset.song_metadata.columns = json.dumps(validation.columns)
                metrics = dataset.song_metrics
                metrics.number_of_songs = summary["number_of_songs"]
                metrics.number_of_artists = summary["number_of_artists"]
                metrics.average_streams = summary["average_stream"]
                metrics.average_views = summary["average_views"]
                metrics.average_likes = summary["average_likes"]
                db.session.commit()
                return dataset
            except Exception:
                db.session.rollback()
                raise

    @staticmethod
    def _parse_publication_type(value: str | None) -> PublicationType:
        if not value:
            return PublicationType.NONE
        return PublicationType(value)

    @classmethod
    def _dataset_metadata(cls, data: dict):
        return DSMetaData(
            title=data["title"],
            description=data["description"],
            publication_type=cls._parse_publication_type(data.get("publication_type")),
            publication_doi=(data.get("publication_doi") or "").strip() or None,
            dataset_doi=(data.get("dataset_doi") or "").strip() or None,
            tags=(data.get("tags") or "").strip() or None,
        )

    def preview_file(self, file_path: str, limit: int = 50) -> list[dict]:
        """Return a bounded preview suitable for the interactive table."""

        self.validate_file(file_path)
        with open(file_path, "r", encoding="utf-8-sig", newline="") as stream:
            rows = []
            for idx, row in enumerate(csv.DictReader(stream)):
                if idx >= limit:
                    break
                rows.append(row)
            return rows

    def get_dataset_preview(
        self,
        dataset: SongDataset,
        limit: int = 50,
        offset: int = 0,
        query: str = "",
    ) -> dict:
        """Return paginated rows and stored summary metrics without re-validating the CSV."""

        path = dataset.file_path()
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

        metrics = dataset.song_metrics
        avg_streams = metrics.average_streams if metrics and metrics.average_streams is not None else 0.0
        avg_views = metrics.average_views if metrics and metrics.average_views is not None else 0.0
        avg_likes = metrics.average_likes if metrics and metrics.average_likes is not None else 0.0
        summary = {
            "number_of_songs": metrics.number_of_songs if metrics else 0,
            "number_of_artists": metrics.number_of_artists if metrics else 0,
            "average_streams": avg_streams,
            "average_stream": avg_streams,
            "average_views": avg_views,
            "average_likes": avg_likes,
        }

        terms = [term.casefold() for term in (query or "").split() if term.strip()]
        searchable = ("Artist", "Track", "Album", "Channel")
        total = 0
        rows = []
        with open(path, "r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if terms:
                    text = " ".join((row.get(field) or "") for field in searchable).casefold()
                    if not all(term in text for term in terms):
                        continue
                if offset <= total < offset + limit:
                    rows.append(row)
                total += 1

        return {
            "rows": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
            "summary": summary,
        }

    def contains_query(self, file_path: str, query: str) -> bool:
        """Search artist, track, album and channel fields without loading all rows."""

        terms = [term.casefold() for term in query.split() if term.strip()]
        if not terms:
            return True
        if not os.path.isfile(file_path):
            return False
        searchable = ("Artist", "Track", "Album", "Channel", "Title", "Description")
        try:
            with open(file_path, "r", encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    text = " ".join((row.get(field) or "") for field in searchable).casefold()
                    if all(term in text for term in terms):
                        return True
        except (OSError, csv.Error, UnicodeDecodeError):
            return False
        return False

    def summarize_file(self, file_path: str) -> dict[str, float]:
        """Calculate the principal Spotify and YouTube aggregates."""

        self.validate_file(file_path)
        with open(file_path, "r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        summary = {}
        for column in ("Stream", "Views", "Likes", "Comments", "Danceability", "Energy"):
            values = [float(row[column]) for row in rows if (row.get(column) or "").strip()]
            summary[f"average_{column.lower()}"] = sum(values) / len(values) if values else 0.0
        summary["average_streams"] = summary["average_stream"]
        summary["number_of_songs"] = len(rows)
        summary["number_of_artists"] = len({row["Artist"] for row in rows if (row.get("Artist") or "").strip()})
        return summary
