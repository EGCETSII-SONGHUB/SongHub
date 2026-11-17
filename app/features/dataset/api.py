from splent_framework.resources.generic_resource import create_resource
from splent_framework.serialisers.serializer import Serializer

from app.features.dataset.models import DataSet

file_fields = {"file_id": "id", "file_name": "name", "size": "get_formatted_size"}
file_serializer = Serializer(file_fields)

dataset_fields = {
    "dataset_id": "id",
    "created": "created_at",
    "name": "name",
    "doi": "get_uvlhub_doi",
    "files": "files",
}

dataset_serializer = Serializer(dataset_fields, related_serializers={"files": file_serializer})

DataSetResource = create_resource(DataSet, dataset_serializer)


class LegacyDataSetResource(DataSetResource):
    """Keep the public API error wording stable after the ORM rename."""

    def __init__(self):
        super().__init__()
        self.model_name = "DataSet"


def init_blueprint_api(api):
    """Function to register resources with the provided Flask-RESTful Api instance."""
    api.add_resource(LegacyDataSetResource, "/api/v1/datasets/", endpoint="datasets")
    api.add_resource(LegacyDataSetResource, "/api/v1/datasets/<int:id>", endpoint="dataset")
