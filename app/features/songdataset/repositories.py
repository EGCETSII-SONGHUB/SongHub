from splent_framework.repositories.BaseRepository import BaseRepository

from app.features.songdataset.models import SongDataset, SongFile, SongMetadata, SongMetrics


class SongDatasetRepository(BaseRepository):
    def __init__(self):
        super().__init__(SongDataset)

    def get_for_owner(self, dataset_id: int, user_id: int) -> SongDataset | None:
        return self.model.query.filter_by(id=dataset_id, user_id=user_id).first()


class SongMetadataRepository(BaseRepository):
    def __init__(self):
        super().__init__(SongMetadata)


class SongMetricsRepository(BaseRepository):
    def __init__(self):
        super().__init__(SongMetrics)


class SongFileRepository(BaseRepository):
    def __init__(self):
        super().__init__(SongFile)
