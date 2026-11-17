from app import db
from app.features.dataset.models import BaseDataset


class SongMetrics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number_of_songs = db.Column(db.Integer, nullable=False, default=0)
    number_of_artists = db.Column(db.Integer, nullable=False, default=0)
    average_streams = db.Column(db.Float, nullable=True)
    average_views = db.Column(db.Float, nullable=True)
    average_likes = db.Column(db.Float, nullable=True)


class SongMetadata(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    csv_filename = db.Column(db.String(255), nullable=False)
    columns = db.Column(db.Text, nullable=False)
    song_metrics_id = db.Column(db.Integer, db.ForeignKey("song_metrics.id"), nullable=False)
    song_metrics = db.relationship("SongMetrics", uselist=False, cascade="all, delete")


class SongFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    checksum = db.Column(db.String(120), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    dataset_id = db.Column(db.Integer, db.ForeignKey("data_set.id"), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "checksum": self.checksum,
            "size_in_bytes": self.size,
        }

    def get_formatted_size(self):
        from app.features.dataset.services import SizeService

        return SizeService().get_human_readable_size(self.size)


class SongDataset(BaseDataset):
    """Dataset containing tabular Spotify and YouTube song measurements."""

    __tablename__ = "song_dataset"
    id = db.Column(db.Integer, db.ForeignKey("data_set.id"), primary_key=True)
    song_metadata_id = db.Column(db.Integer, db.ForeignKey("song_metadata.id"), nullable=False)
    song_metadata = db.relationship("SongMetadata", uselist=False, cascade="all, delete")
    song_files = db.relationship("SongFile", backref="song_dataset", cascade="all, delete", lazy=True)

    __mapper_args__ = {"polymorphic_identity": "song"}

    @property
    def song_metrics(self):
        return self.song_metadata.song_metrics

    def files(self):
        return self.song_files

    def get_files_count(self):
        return len(self.song_files)

    def get_file_total_size(self):
        return sum(file.size for file in self.song_files)

    def contains_query(self, query: str, working_dir: str = "") -> bool:
        from app.features.songdataset.services import SongDatasetService

        if not self.song_metadata or not self.song_files:
            return False
        path = (
            f"{working_dir}/uploads/user_{self.user_id}/dataset_{self.id}/"
            f"{self.song_metadata.csv_filename}"
        )
        return SongDatasetService().contains_query(path, query)
