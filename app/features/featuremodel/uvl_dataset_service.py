import hashlib
import os
import shutil

from app.features.dataset.models import UVLDataset
from app.features.dataset.repositories import AuthorRepository, DataSetRepository, DSMetaDataRepository
from app.features.featuremodel.repositories import FeatureModelRepository, FMMetaDataRepository
from app.features.hubfile.repositories import HubfileRepository


class UVLDatasetService:
    """UVL-specific persistence and temporary-file operations."""

    def __init__(self):
        self.repository = DataSetRepository()
        self.feature_model_repository = FeatureModelRepository()
        self.author_repository = AuthorRepository()
        self.fmmetadata_repository = FMMetaDataRepository()
        self.hubfilerepository = HubfileRepository()

    def create_from_form(self, form, current_user) -> UVLDataset:
        main_author = {
            "name": f"{current_user.profile.surname}, {current_user.profile.name}",
            "affiliation": current_user.profile.affiliation,
            "orcid": current_user.profile.orcid,
        }
        dsmetadata = DSMetaDataRepository().create(**form.get_dsmetadata())
        for author_data in [main_author] + form.get_authors():
            author = self.author_repository.create(
                commit=False, ds_meta_data_id=dsmetadata.id, **author_data
            )
            dsmetadata.authors.append(author)
        dataset = UVLDataset(user_id=current_user.id, ds_meta_data_id=dsmetadata.id)
        self.repository.session.add(dataset)
        self.repository.session.flush()
        for feature_model in form.feature_models:
            filename = feature_model.uvl_filename.data
            metadata = self.fmmetadata_repository.create(
                commit=False, **feature_model.get_fmmetadata()
            )
            for author_data in feature_model.get_authors():
                metadata.authors.append(
                    self.author_repository.create(
                        commit=False, fm_meta_data_id=metadata.id, **author_data
                    )
                )
            model = self.feature_model_repository.create(
                commit=False, data_set_id=dataset.id, fm_meta_data_id=metadata.id
            )
            source = os.path.join(current_user.temp_folder(), filename)
            with open(source, "rb") as stream:
                checksum = hashlib.md5(stream.read()).hexdigest()
            model.files.append(
                self.hubfilerepository.create(
                    commit=False,
                    name=filename,
                    checksum=checksum,
                    size=os.path.getsize(source),
                    feature_model_id=model.id,
                )
            )
        self.repository.session.commit()
        return dataset

    def move_files(self, dataset: UVLDataset, current_user) -> None:
        destination = os.path.join(
            os.getenv("WORKING_DIR", ""),
            "uploads",
            f"user_{current_user.id}",
            f"dataset_{dataset.id}",
        )
        os.makedirs(destination, exist_ok=True)
        for model in dataset.feature_models:
            shutil.move(
                os.path.join(current_user.temp_folder(), model.fm_meta_data.uvl_filename),
                destination,
            )

    def save_temp_uvl(self, file, current_user) -> dict:
        if not file or not file.filename.endswith(".uvl"):
            return {"status": "error", "code": 400, "message": "No valid file"}
        folder = current_user.temp_folder()
        os.makedirs(folder, exist_ok=True)
        filename = file.filename
        target = os.path.join(folder, filename)
        index = 1
        base, extension = os.path.splitext(filename)
        while os.path.exists(target):
            filename = f"{base} ({index}){extension}"
            target = os.path.join(folder, filename)
            index += 1
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
