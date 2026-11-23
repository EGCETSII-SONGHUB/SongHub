import re

import unidecode
from splent_framework.repositories.BaseRepository import BaseRepository
from sqlalchemy import or_

from app.features.dataset.models import Author, BaseDataset, DSMetaData, PublicationType
from app.features.featuremodel.models import FeatureModel, FMMetaData
from app.features.songdataset.models import SongDataset, SongMetadata


class ExploreRepository(BaseRepository):
    def __init__(self):
        super().__init__(BaseDataset)

    def filter(self, query="", sorting="newest", publication_type="any", tags=None, dataset_type="any", **kwargs):
        tags = tags or []
        normalized_query = unidecode.unidecode(query).lower()
        cleaned_query = re.sub(r'[,.":\'()\[\]^;!¡¿?]', "", normalized_query)
        words = cleaned_query.split()

        base_query = (
            self.model.query.join(BaseDataset.ds_meta_data)
            .outerjoin(DSMetaData.authors)
            .outerjoin(FeatureModel, FeatureModel.data_set_id == BaseDataset.id)
            .outerjoin(FeatureModel.fm_meta_data)
            .outerjoin(SongDataset.__table__, SongDataset.__table__.c.id == BaseDataset.id)
            .outerjoin(SongMetadata, SongMetadata.id == SongDataset.__table__.c.song_metadata_id)
            .filter(DSMetaData.dataset_doi.isnot(None))
            .filter(or_(FeatureModel.id.isnot(None), SongDataset.__table__.c.id.isnot(None)))
        )

        if publication_type != "any":
            matching_type = None
            for member in PublicationType:
                if member.value.lower() == publication_type:
                    matching_type = member
                    break
            if matching_type is not None:
                base_query = base_query.filter(DSMetaData.publication_type == matching_type.name)

        if tags:
            base_query = base_query.filter(or_(*(DSMetaData.tags.ilike(f"%{tag}%") for tag in tags)))

        if dataset_type == "uvl":
            base_query = base_query.filter(BaseDataset.dataset_type.in_(("uvl", "base")))
        elif dataset_type == "song":
            base_query = base_query.filter(BaseDataset.dataset_type == "song")

        order_col = BaseDataset.created_at.asc() if sorting == "oldest" else BaseDataset.created_at.desc()

        if not words:
            return base_query.distinct().order_by(order_col).all()

        filters = []
        for word in words:
            filters.extend(
                [
                    DSMetaData.title.ilike(f"%{word}%"),
                    DSMetaData.description.ilike(f"%{word}%"),
                    Author.name.ilike(f"%{word}%"),
                    Author.affiliation.ilike(f"%{word}%"),
                    Author.orcid.ilike(f"%{word}%"),
                    FMMetaData.uvl_filename.ilike(f"%{word}%"),
                    FMMetaData.title.ilike(f"%{word}%"),
                    FMMetaData.description.ilike(f"%{word}%"),
                    FMMetaData.publication_doi.ilike(f"%{word}%"),
                    FMMetaData.tags.ilike(f"%{word}%"),
                    DSMetaData.tags.ilike(f"%{word}%"),
                    SongMetadata.csv_filename.ilike(f"%{word}%"),
                ]
            )

        sql_ids = {row[0] for row in base_query.filter(or_(*filters)).with_entities(BaseDataset.id).distinct().all()}

        csv_ids = set()
        if dataset_type in {"any", "song"}:
            song_candidates = base_query.filter(BaseDataset.dataset_type == "song").distinct().all()
            for dataset in song_candidates:
                if dataset.id not in sql_ids and dataset.contains_query(query):
                    csv_ids.add(dataset.id)

        matched_ids = sql_ids | csv_ids
        if not matched_ids:
            return []

        return base_query.filter(BaseDataset.id.in_(matched_ids)).distinct().order_by(order_col).all()
