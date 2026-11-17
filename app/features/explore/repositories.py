import re
import os

import unidecode
from splent_framework.repositories.BaseRepository import BaseRepository
from sqlalchemy import or_

from app.features.dataset.models import Author, DataSet, DSMetaData, PublicationType
from app.features.featuremodel.models import FeatureModel, FMMetaData
from app.features.songdataset.models import SongDataset, SongMetadata


class ExploreRepository(BaseRepository):
    def __init__(self):
        super().__init__(DataSet)

    def filter(self, query="", sorting="newest", publication_type="any", tags=None, dataset_type="any", **kwargs):
        tags = tags or []
        # Normalize and remove unwanted characters
        normalized_query = unidecode.unidecode(query).lower()
        cleaned_query = re.sub(r'[,.":\'()\[\]^;!¡¿?]', "", normalized_query)

        filters = []
        for word in cleaned_query.split():
            filters.append(DSMetaData.title.ilike(f"%{word}%"))
            filters.append(DSMetaData.description.ilike(f"%{word}%"))
            filters.append(Author.name.ilike(f"%{word}%"))
            filters.append(Author.affiliation.ilike(f"%{word}%"))
            filters.append(Author.orcid.ilike(f"%{word}%"))
            filters.append(FMMetaData.uvl_filename.ilike(f"%{word}%"))
            filters.append(FMMetaData.title.ilike(f"%{word}%"))
            filters.append(FMMetaData.description.ilike(f"%{word}%"))
            filters.append(FMMetaData.publication_doi.ilike(f"%{word}%"))
            filters.append(FMMetaData.tags.ilike(f"%{word}%"))
            filters.append(DSMetaData.tags.ilike(f"%{word}%"))
            filters.append(SongMetadata.csv_filename.ilike(f"%{word}%"))

        datasets = (
            self.model.query.join(DataSet.ds_meta_data)
            .outerjoin(DSMetaData.authors)
            .outerjoin(DataSet.feature_models)
            .outerjoin(FeatureModel.fm_meta_data)
            .outerjoin(SongDataset.__table__, SongDataset.__table__.c.id == DataSet.id)
            .outerjoin(SongMetadata, SongMetadata.id == SongDataset.__table__.c.song_metadata_id)
            .filter(DSMetaData.dataset_doi.isnot(None))  # Exclude datasets with empty dataset_doi
            .filter(or_(FeatureModel.id.isnot(None), SongDataset.__table__.c.id.isnot(None)))
        )
        if filters and not (query and dataset_type == "song"):
            datasets = datasets.filter(or_(*filters))
        datasets = datasets.distinct()

        if publication_type != "any":
            matching_type = None
            for member in PublicationType:
                if member.value.lower() == publication_type:
                    matching_type = member
                    break

            if matching_type is not None:
                datasets = datasets.filter(DSMetaData.publication_type == matching_type.name)

        if tags:
            datasets = datasets.filter(or_(*(DSMetaData.tags.ilike(f"%{tag}%") for tag in tags)))
        if dataset_type in {"uvl", "song"}:
            datasets = datasets.filter(DataSet.dataset_type == dataset_type)

        # Order by created_at
        if sorting == "oldest":
            datasets = datasets.order_by(self.model.created_at.asc())
        else:
            datasets = datasets.order_by(self.model.created_at.desc())

        results = datasets.all()
        if query and dataset_type in {"any", "song"}:
            results = [
                dataset
                for dataset in results
                if dataset.dataset_type != "song"
                or dataset.contains_query(query, os.getenv("WORKING_DIR", ""))
            ]
        return results
