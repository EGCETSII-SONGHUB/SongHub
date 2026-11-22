import os
import uuid

from splent_framework.configuration.configuration import uploads_folder_name
from splent_framework.services.BaseService import BaseService
from sqlalchemy import func
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.features.auth.models import User
from app.features.auth.repositories import UserRepository
from app.features.community.models import Community, CommunityDatasetRequest
from app.features.community.repositories import CommunityDatasetRequestRepository, CommunityRepository
from app.features.dataset.models import DataSet
from app.features.dataset.repositories import DataSetRepository

ALLOWED_LOGO_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "svg", "webp"})
_INVALID_LOGO_MSG = "Logo must be an image file (png, jpg, jpeg, gif, svg, webp)."


def normalize_community_name(name: str | None) -> str:
    """Strip surrounding whitespace from a community name."""
    return (name or "").strip()


def is_allowed_logo_filename(filename: str | None) -> bool:
    """Return True if *filename* has a supported image extension."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_LOGO_EXTENSIONS


def build_logo_storage_filename(original_filename: str) -> str:
    """Build a collision-free filename preserving a validated image extension."""
    sanitized = secure_filename(original_filename or "")
    if not is_allowed_logo_filename(sanitized):
        raise ValueError(_INVALID_LOGO_MSG)
    ext = sanitized.rsplit(".", 1)[1].lower()
    return f"community_{uuid.uuid4().hex}.{ext}"


class CommunityService(BaseService):
    """Business logic for creating, editing, listing, and curating communities."""

    def __init__(self):
        super().__init__(CommunityRepository())
        self.dataset_repository = DataSetRepository()
        self.user_repository = UserRepository()
        self.request_repository = CommunityDatasetRequestRepository()

    def logos_directory(self) -> str:
        """Return the directory where uploaded community logos are stored."""
        working_dir = os.getenv("WORKING_DIR", "")
        return os.path.join(working_dir, uploads_folder_name(), "communities")

    def _save_logo_file(self, logo_file: FileStorage) -> str:
        if not is_allowed_logo_filename(logo_file.filename):
            raise ValueError(_INVALID_LOGO_MSG)
        logos_dir = self.logos_directory()
        os.makedirs(logos_dir, exist_ok=True)
        stored_name = build_logo_storage_filename(logo_file.filename)
        logo_file.save(os.path.join(logos_dir, stored_name))
        return stored_name

    def _delete_local_logo(self, logo_value: str | None) -> None:
        if not logo_value or logo_value.startswith(("http://", "https://", "/")):
            return
        logo_path = os.path.join(self.logos_directory(), os.path.basename(logo_value))
        if os.path.isfile(logo_path):
            os.remove(logo_path)

    def _validate_text_fields(self, form, exclude_community_id: int | None = None) -> tuple[str, str, dict | None]:
        if not form.validate():
            return "", "", form.errors

        name = normalize_community_name(form.name.data)
        description = (form.description.data or "").strip()
        errors: dict[str, list[str]] = {}
        if not name:
            errors["name"] = ["This field is required."]
        if not description:
            errors["description"] = ["This field is required."]
        if errors:
            return "", "", errors

        existing = self.repository.get_by_name(name)
        if existing and existing.id != exclude_community_id:
            return "", "", {"name": ["A community with this name already exists."]}

        return name, description, None

    def _resolve_uploaded_logo(self, form, logo_file: FileStorage | None) -> tuple[FileStorage | None, dict | None]:
        candidate = logo_file if logo_file is not None else form.logo.data
        if not isinstance(candidate, FileStorage) or not candidate.filename:
            return None, None
        if not is_allowed_logo_filename(candidate.filename):
            return None, {"logo": [_INVALID_LOGO_MSG]}
        return candidate, None

    def list_communities(self) -> list[Community]:
        """Return all communities ordered newest first."""
        return self.repository.get_all_ordered()

    def create_community(
        self, form, creator, logo_file: FileStorage | None = None
    ) -> tuple[Community | None, dict | None]:
        """Validate *form*, persist a new community, and register *creator* as initial curator."""
        name, description, errors = self._validate_text_fields(form)
        if errors:
            return None, errors

        uploaded_logo, logo_errors = self._resolve_uploaded_logo(form, logo_file)
        if logo_errors:
            return None, logo_errors

        saved_logo = self._save_logo_file(uploaded_logo) if uploaded_logo is not None else None

        try:
            community = self.repository.create(
                commit=False,
                name=name,
                description=description,
                logo=saved_logo,
                creator_id=creator.id,
            )
            community.curators.append(creator)
            self.repository.session.commit()
        except Exception:
            self.repository.session.rollback()
            self._delete_local_logo(saved_logo)
            raise

        return community, None

    def update_community(
        self,
        community: Community,
        form,
        editor,
        logo_file: FileStorage | None = None,
    ) -> tuple[Community | None, dict | None]:
        """Update an existing community if *editor* is one of its curators."""
        if not community.is_curator(editor):
            raise PermissionError("Only curators can edit this community.")

        name, description, errors = self._validate_text_fields(form, exclude_community_id=community.id)
        if errors:
            return None, errors

        uploaded_logo, logo_errors = self._resolve_uploaded_logo(form, logo_file)
        if logo_errors:
            return None, logo_errors

        old_logo = community.logo
        new_logo = self._save_logo_file(uploaded_logo) if uploaded_logo is not None else None

        try:
            community.name = name
            community.description = description
            if new_logo is not None:
                community.logo = new_logo
            self.repository.session.commit()
        except Exception:
            self.repository.session.rollback()
            self._delete_local_logo(new_logo)
            raise

        if new_logo is not None:
            self._delete_local_logo(old_logo)

        return community, None

    def propose_dataset(self, community: Community, dataset_id: int, user) -> CommunityDatasetRequest:
        """Create a pending request to add one of the user's dataset to the community"""
        dataset = self.dataset_repository.get_by_id(dataset_id)
        if dataset is None:
            raise LookupError("Dataset not found.")
        if dataset.user_id != user.id:
            raise PermissionError("Only the owner of a dataset can propose it to a community.")
        if dataset in community.datasets:
            raise ValueError("This dataset is already in the community.")
        if self.request_repository.get_pending(community.id, dataset.id):
            raise ValueError("There is already a pending request for this dataset.")

        request = CommunityDatasetRequest(community_id=community.id, dataset_id=dataset.id, requester_id=user.id)
        self.repository.session.add(request)
        self.repository.session.commit()
        return request

    def _resolve_request(self, request: CommunityDatasetRequest, curator, status: str, comment: str | None):
        if not request.community.is_curator(curator):
            raise PermissionError("Only curators can resolve requests.")
        if not request.is_pending():
            raise ValueError("This request has already been resolved.")

        request.resolve(status, curator, comment)
        if status == CommunityDatasetRequest.STATUS_ACCEPTED and request.dataset not in request.community.datasets:
            request.community.datasets.append(request.dataset)
        self.repository.session.commit()
        return request

    def accept_request(self, request, curator, comment: str | None = None):
        return self._resolve_request(request, curator, CommunityDatasetRequest.STATUS_ACCEPTED, comment)

    def reject_request(self, request, curator, comment: str | None = None):
        return self._resolve_request(request, curator, CommunityDatasetRequest.STATUS_REJECTED, comment)

    def list_pending_requests(self, community: Community, curator) -> list[CommunityDatasetRequest]:
        if not community.is_curator(curator):
            raise PermissionError("Only curators can see pending requests.")
        return self.request_repository.get_pending_by_community(community.id)

    def list_user_requests(self, user) -> list[CommunityDatasetRequest]:
        return self.request_repository.get_by_requester(user.id)

    def remove_dataset(self, community: Community, dataset_id: int, user) -> None:
        """Remove *dataset_id* from *community* if *user* owns the dataset or curates the community."""
        dataset = self.dataset_repository.get_by_id(dataset_id)
        if dataset is None:
            raise LookupError("Dataset not found.")
        if dataset.user_id != user.id and not community.is_curator(user):
            raise PermissionError("Not authorized to remove this dataset.")

        if dataset in community.datasets:
            community.datasets.remove(dataset)
            self.repository.session.commit()

    def add_curator(self, community: Community, new_curator, actor) -> None:
        """Grant curator status on *community* to *new_curator* when requested by an existing curator."""
        if not community.is_curator(actor):
            raise PermissionError("Only curators can add curators.")
        if new_curator not in community.curators:
            community.curators.append(new_curator)
            self.repository.session.commit()

    def add_curator_by_email(self, community: Community, email: str, actor) -> tuple[User | None, str | None]:
        """Grant curator status to the user matching *email*, returning *(user, error_message)*."""
        if not community.is_curator(actor):
            raise PermissionError("Only curators can add curators.")

        clean_email = (email or "").strip()
        target_user = User.query.filter(func.lower(User.email) == clean_email.lower()).first()
        if target_user is None:
            return None, f"No user found with email '{clean_email}'."

        if target_user not in community.curators:
            community.curators.append(target_user)
            self.repository.session.commit()
        return target_user, None

    def remove_curator(self, community: Community, curator_id: int, actor) -> tuple[bool, str | None]:
        """Remove *curator_id* from *community*, always preserving at least one curator."""
        if not community.is_curator(actor):
            raise PermissionError("Only curators can remove curators.")

        target = next((curator for curator in community.curators if curator.id == curator_id), None)
        if target is None:
            raise LookupError("Curator not found in this community.")

        if len(community.curators) <= 1:
            return False, "A community must have at least one curator."

        community.curators.remove(target)
        self.repository.session.commit()
        return True, None

    def get_available_datasets_for_user(self, community: Community, user_id: int) -> list[DataSet]:
        """Return *user_id*'s datasets not yet linked to *community*, newest first."""
        linked_ids = {dataset.id for dataset in community.datasets}
        linked_ids |= {r.dataset_id for r in self.request_repository.get_pending_by_community(community.id)}
        user_datasets = DataSet.query.filter_by(user_id=user_id).order_by(DataSet.created_at.desc()).all()
        return [dataset for dataset in user_datasets if dataset.id not in linked_ids]
