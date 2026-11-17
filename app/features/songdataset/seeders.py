import json
import hashlib
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from splent_framework.seeders.BaseSeeder import BaseSeeder

from app import db
from app.features.auth.models import User
from app.features.dataset.models import Author, DSMetaData, PublicationType
from app.features.songdataset.models import SongDataset, SongFile, SongMetadata, SongMetrics
from app.features.songdataset.services import SongDatasetService


class SongDatasetSeeder(BaseSeeder):

    priority = 3

    def run(self):
        load_dotenv()
        source = os.path.join(os.path.dirname(__file__), "song_examples", "Spotify_Youtube.csv")
        if not os.path.exists(source):
            return
        user = User.query.filter_by(email="songhub@example.com").first()
        if not user:
            user = User(email="songhub@example.com", password="1234")
            db.session.add(user)
            db.session.flush()
        dataset = SongDataset.query.join(SongDataset.ds_meta_data).filter(
            DSMetaData.title == "Spotify and YouTube sample"
        ).first()
        service = SongDatasetService()
        summary = service.summarize_file(source)
        validation = service.validate_file(source)
        metrics = SongMetrics(
            number_of_songs=summary["number_of_songs"],
            number_of_artists=summary["number_of_artists"],
            average_streams=summary["average_stream"],
            average_views=summary["average_views"],
            average_likes=summary["average_likes"],
        )
        if dataset is None:
            metadata = SongMetadata(
                csv_filename=Path(source).name,
                columns=json.dumps(validation.columns),
                song_metrics=metrics,
            )
            common = DSMetaData(
                title="Spotify and YouTube sample",
                description="Complete Spotify and YouTube dataset for SongHub.",
                publication_type=PublicationType.NONE,
                publication_doi="10.1234/songhub-sample",
                dataset_doi="10.1234/songhub-sample",
                tags="spotify, youtube, music",
                authors=[Author(name="SongHub Demo")],
            )
            dataset = SongDataset(
                user_id=user.id, dataset_type="song", ds_meta_data=common, song_metadata=metadata
            )
        else:
            dataset.song_metadata.csv_filename = Path(source).name
            dataset.song_metadata.columns = json.dumps(validation.columns)
            dataset.song_metrics.number_of_songs = metrics.number_of_songs
            dataset.song_metrics.number_of_artists = metrics.number_of_artists
            dataset.song_metrics.average_streams = metrics.average_streams
            dataset.song_metrics.average_views = metrics.average_views
            dataset.song_metrics.average_likes = metrics.average_likes
            dataset.ds_meta_data.description = "Complete Spotify and YouTube dataset for SongHub."
        with open(source, "rb") as stream:
            checksum = hashlib.md5(stream.read()).hexdigest()
        if dataset.song_files:
            dataset.song_files[0].name = Path(source).name
            dataset.song_files[0].checksum = checksum
            dataset.song_files[0].size = os.path.getsize(source)
        else:
            dataset.song_files.append(
                SongFile(name=Path(source).name, checksum=checksum, size=os.path.getsize(source))
            )
        db.session.add(dataset)
        db.session.commit()
        destination = os.path.join(os.getenv("WORKING_DIR", ""), "uploads", f"user_{user.id}", f"dataset_{dataset.id}")
        os.makedirs(destination, exist_ok=True)
        shutil.copy(source, os.path.join(destination, Path(source).name))
        return dataset
