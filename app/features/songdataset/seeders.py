import hashlib
import json
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from splent_framework.seeders.BaseSeeder import BaseSeeder

from app import db
from app.features.auth.models import User
from app.features.dataset.models import Author, DSMetaData, PublicationType
from app.features.profile.models import UserProfile
from app.features.songdataset.models import SongDataset, SongFile, SongMetadata, SongMetrics
from app.features.songdataset.services import SongDatasetService

SEED_SPECS = (
    {
        "filename": "spotify_youtube_rock_alt.csv",
        "title": "Spotify and YouTube Rock & Alternative",
        "description": (
            "Subset of rock and alternative tracks with Spotify audio features and YouTube engagement metrics."
        ),
        "publication_doi": "10.1234/songhub-sample",
        "dataset_doi": "10.1234/songhub-sample",
        "deposition_id": 101,
        "tags": "spotify, youtube, rock",
    },
    {
        "filename": "spotify_youtube_pop_hits.csv",
        "title": "Spotify and YouTube Pop & Dance",
        "description": "Subset of pop and dance tracks with Spotify audio features and YouTube engagement metrics.",
        "publication_doi": "10.1234/songhub-pop",
        "dataset_doi": "10.1234/songhub-pop",
        "deposition_id": 102,
        "tags": "spotify, youtube, pop",
    },
)


class SongDatasetSeeder(BaseSeeder):

    priority = 3

    def run(self):
        load_dotenv()
        user = User.query.filter_by(email="songhub@example.com").first()
        if not user:
            user = User(email="songhub@example.com", password="1234")
            db.session.add(user)
            db.session.flush()
        if user.profile is None:
            profile = UserProfile(
                user_id=user.id,
                name="Music",
                surname="Curator",
                affiliation="SongHub",
                orcid="0000-0000-0000-0099",
            )
            db.session.add(profile)
            db.session.flush()

        service = SongDatasetService()
        seeded = []
        examples_dir = os.path.join(os.path.dirname(__file__), "song_examples")

        for spec in SEED_SPECS:
            source = os.path.join(examples_dir, spec["filename"])
            if not os.path.exists(source):
                continue

            validation = service.validate_file(source)
            summary = service.summarize_file(source)
            with open(source, "rb") as stream:
                checksum = hashlib.md5(stream.read()).hexdigest()
            size = os.path.getsize(source)
            csv_name = Path(source).name

            dataset = (
                SongDataset.query.join(SongDataset.ds_meta_data)
                .filter(DSMetaData.dataset_doi == spec["dataset_doi"])
                .first()
            )
            if dataset is None:
                metrics = SongMetrics(
                    number_of_songs=summary["number_of_songs"],
                    number_of_artists=summary["number_of_artists"],
                    average_streams=summary["average_stream"],
                    average_views=summary["average_views"],
                    average_likes=summary["average_likes"],
                )
                metadata = SongMetadata(
                    csv_filename=csv_name,
                    columns=json.dumps(validation.columns),
                    song_metrics=metrics,
                )
                common = DSMetaData(
                    deposition_id=spec["deposition_id"],
                    title=spec["title"],
                    description=spec["description"],
                    publication_type=PublicationType.NONE,
                    publication_doi=spec["publication_doi"],
                    dataset_doi=spec["dataset_doi"],
                    tags=spec["tags"],
                    authors=[Author(name="Curator, Music", affiliation="SongHub")],
                )
                dataset = SongDataset(
                    user_id=user.id,
                    dataset_type="song",
                    ds_meta_data=common,
                    song_metadata=metadata,
                )
                dataset.song_files.append(SongFile(name=csv_name, checksum=checksum, size=size))
                db.session.add(dataset)
            else:
                dataset.song_metadata.csv_filename = csv_name
                dataset.song_metadata.columns = json.dumps(validation.columns)
                dataset.song_metrics.number_of_songs = summary["number_of_songs"]
                dataset.song_metrics.number_of_artists = summary["number_of_artists"]
                dataset.song_metrics.average_streams = summary["average_stream"]
                dataset.song_metrics.average_views = summary["average_views"]
                dataset.song_metrics.average_likes = summary["average_likes"]
                dataset.ds_meta_data.deposition_id = spec["deposition_id"]
                dataset.ds_meta_data.title = spec["title"]
                dataset.ds_meta_data.description = spec["description"]
                dataset.ds_meta_data.publication_doi = spec["publication_doi"]
                dataset.ds_meta_data.tags = spec["tags"]
                if not dataset.ds_meta_data.authors:
                    dataset.ds_meta_data.authors.append(Author(name="Curator, Music", affiliation="SongHub"))
                if dataset.song_files:
                    dataset.song_files[0].name = csv_name
                    dataset.song_files[0].checksum = checksum
                    dataset.song_files[0].size = size
                else:
                    dataset.song_files.append(SongFile(name=csv_name, checksum=checksum, size=size))

            db.session.commit()
            destination = os.path.join(
                os.getenv("WORKING_DIR", ""),
                "uploads",
                f"user_{user.id}",
                f"dataset_{dataset.id}",
            )
            os.makedirs(destination, exist_ok=True)
            shutil.copy2(source, os.path.join(destination, csv_name))
            seeded.append(dataset)

        return seeded
