from splent_framework.services.BaseService import BaseService

from app.features.explore.repositories import ExploreRepository


class ExploreService(BaseService):
    def __init__(self):
        super().__init__(ExploreRepository())

    def filter(self, query="", sorting="newest", publication_type="any", tags=None, dataset_type="any", **kwargs):
        return self.repository.filter(query, sorting, publication_type, tags, dataset_type, **kwargs)
