import csv
import hashlib
import json
import os
import shutil
from pathlib import Path

from app.features.songdataset.validation import SongCSVValidationError, validate_song_csv
from app import db
from app.features.dataset.models import Author, PublicationType
from app.features.songdataset.models import SongDataset, SongFile, SongMetadata, SongMetrics


class SongDatasetService:


    def validate_file(self, file_path: str):
        if Path(file_path).suffix.lower() != ".csv":
            raise SongCSVValidationError("Song datasets must be CSV files")
        with open(file_path, "r", encoding="utf-8-sig", newline="") as stream:
            return validate_song_csv(stream)

    def save_temp_csv(self, file, current_user) -> dict:
        if not file or not file.filename.lower().endswith(".csv"):
            return {"status": "error", "code": 400, "message": "No valid CSV file"}
        folder = current_user.temp_folder()
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, os.path.basename(file.filename))
        try:
            file.save(target)
            result = self.validate_file(target)
        except (OSError, SongCSVValidationError) as exc:
            if os.path.exists(target):
                os.remove(target)
            return {"status": "error", "code": 400, "message": str(exc)}
        return {
            "status": "ok",
            "code": 200,
            "message": "Song CSV uploaded and validated successfully",
            "filename": os.path.basename(target),
            "rows": result.rows,
        }

    def create_from_upload(self, form_data: dict, filename: str, current_user) -> SongDataset:
        source = os.path.join(current_user.temp_folder(), os.path.basename(filename))
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
            csv_filename=os.path.basename(filename),
            columns=json.dumps(validation.columns),
            song_metrics=metrics,
        )
        dataset = SongDataset(
            user_id=current_user.id,
            dataset_type="song",
            ds_meta_data=self._dataset_metadata(form_data),
            song_metadata=metadata,
        )
        dataset.ds_meta_data.authors.append(
            Author(
                name=f"{current_user.profile.surname}, {current_user.profile.name}",
                affiliation=current_user.profile.affiliation,
                orcid=current_user.profile.orcid,
            )
        )
        with open(source, "rb") as stream:
            checksum = hashlib.md5(stream.read()).hexdigest()
        dataset.song_files.append(
            SongFile(name=os.path.basename(filename), checksum=checksum, size=os.path.getsize(source))
        )
        db.session.add(dataset)
        db.session.commit()
        destination = os.path.join(
            os.getenv("WORKING_DIR", ""), "uploads", f"user_{current_user.id}", f"dataset_{dataset.id}"
        )
        os.makedirs(destination, exist_ok=True)
        shutil.copy2(source, os.path.join(destination, os.path.basename(filename)))
        return dataset

    def update_metadata(self, dataset: SongDataset, form_data: dict) -> SongDataset:
        dataset.ds_meta_data.title = form_data["title"]
        dataset.ds_meta_data.description = form_data["description"]
        dataset.ds_meta_data.tags = form_data.get("tags")
        db.session.commit()
        return dataset

    def replace_file(self, dataset: SongDataset, uploaded_file) -> SongDataset:
        """Replace the CSV and atomically refresh validation, metrics and checksum."""

        if not uploaded_file or not uploaded_file.filename.lower().endswith(".csv"):
            raise SongCSVValidationError("Song datasets must be CSV files")
        temp_folder = os.path.join(os.getenv("WORKING_DIR", ""), "song-replacements")
        os.makedirs(temp_folder, exist_ok=True)
        temporary_path = os.path.join(temp_folder, os.path.basename(uploaded_file.filename))
        uploaded_file.save(temporary_path)
        try:
            validation = self.validate_file(temporary_path)
            summary = self.summarize_file(temporary_path)
            with open(temporary_path, "rb") as stream:
                checksum = hashlib.md5(stream.read()).hexdigest()
            destination = os.path.join(
                os.getenv("WORKING_DIR", ""), "uploads", f"user_{dataset.user_id}", f"dataset_{dataset.id}"
            )
            os.makedirs(destination, exist_ok=True)
            old_path = os.path.join(destination, dataset.song_metadata.csv_filename)
            new_name = os.path.basename(uploaded_file.filename)
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
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

    @staticmethod
    def _dataset_metadata(data: dict):
        from app.features.dataset.models import DSMetaData

        publication_type = data.get("publication_type", "none")
        return DSMetaData(
            title=data["title"],
            description=data["description"],
            publication_type=PublicationType(publication_type),
            publication_doi=data.get("publication_doi"),
            dataset_doi=data.get("dataset_doi"),
            tags=data.get("tags"),
        )

    def preview_file(self, file_path: str, limit: int = 50) -> list[dict]:
        """Return a bounded preview suitable for the interactive table."""

        self.validate_file(file_path)
        with open(file_path, "r", encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))[:limit]

    def contains_query(self, file_path: str, query: str) -> bool:
        """Search artist, track, album and channel fields without loading all rows."""

        terms = [term.casefold() for term in query.split() if term.strip()]
        if not terms:
            return True
        self.validate_file(file_path)
        searchable = ("Artist", "Track", "Album", "Channel", "Title", "Description")
        with open(file_path, "r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                text = " ".join(row.get(field, "") for field in searchable).casefold()
                if all(term in text for term in terms):
                    return True
        return False

    def summarize_file(self, file_path: str) -> dict[str, float]:
        """Calculate the principal Spotify and YouTube aggregates."""

        self.validate_file(file_path)
        with open(file_path, "r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        summary = {}
        for column in ("Stream", "Views", "Likes", "Comments", "Danceability", "Energy"):
            values = [float(row[column]) for row in rows if row.get(column)]
            summary[f"average_{column.lower()}"] = sum(values) / len(values) if values else 0.0
        summary["number_of_songs"] = len(rows)
        summary["number_of_artists"] = len({row["Artist"] for row in rows})
        return summary
