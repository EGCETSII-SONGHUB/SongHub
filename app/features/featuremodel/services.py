import os

from splent_framework.services.BaseService import BaseService

from app.features.featuremodel.repositories import FeatureModelRepository, FMMetaDataRepository
from app.features.hubfile.services import HubfileService


class UVLUploadService:
    """UVL-only temporary upload handling kept outside common dataset routes."""

    def save_temp_uvl(self, file, current_user) -> dict:
        if not file or not file.filename.endswith(".uvl"):
            return {"status": "error", "code": 400, "message": "No valid file"}
        temp_folder = current_user.temp_folder()
        os.makedirs(temp_folder, exist_ok=True)
        filename = file.filename
        target = os.path.join(temp_folder, filename)
        if os.path.exists(target):
            base, ext = os.path.splitext(filename)
            index = 1
            while os.path.exists(os.path.join(temp_folder, f"{base} ({index}){ext}")):
                index += 1
            filename = f"{base} ({index}){ext}"
            target = os.path.join(temp_folder, filename)
        try:
            file.save(target)
        except OSError as exc:
            return {"status": "error", "code": 500, "message": str(exc)}
        return {
            "status": "ok",
            "code": 200,
            "message": "UVL uploaded and validated successfully",
            "filename": filename,
        }


class FeatureModelService(BaseService):
    def __init__(self):
        super().__init__(FeatureModelRepository())
        self.hubfile_service = HubfileService()

    def total_feature_model_views(self) -> int:
        return self.hubfile_service.total_hubfile_views()

    def total_feature_model_downloads(self) -> int:
        return self.hubfile_service.total_hubfile_downloads()

    def count_feature_models(self):
        return self.repository.count_feature_models()


class FMMetaDataService(BaseService):
    def __init__(self):
        super().__init__(FMMetaDataRepository())
