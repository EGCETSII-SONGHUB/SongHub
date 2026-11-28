from splent_framework.repositories.BaseRepository import BaseRepository

from app.features.community.models import Community, CommunityDatasetRequest


class CommunityRepository(BaseRepository):
    """Data-access layer for Community records."""

    def __init__(self):
        super().__init__(Community)

    def get_by_name(self, name: str) -> Community | None:
        """Return the community matching *name*, or None."""
        return self.model.query.filter_by(name=name).first()

    def get_all_ordered(self) -> list[Community]:
        """Return all communities ordered newest first."""
        return self.model.query.order_by(self.model.created_at.desc(), self.model.id.desc()).all()

    def get_by_curator(self, user_id: int) -> list[Community]:
        """Return communities curated by *user_id*, newest first."""
        return (
            self.model.query.filter(self.model.curators.any(id=user_id))
            .order_by(self.model.created_at.desc(), self.model.id.desc())
            .all()
        )


class CommunityDatasetRequestRepository(BaseRepository):
    """Data-access layer for community dataset requests."""

    def __init__(self):
        super().__init__(CommunityDatasetRequest)

    def get_pending_by_community(self, community_id: int) -> list[CommunityDatasetRequest]:
        """Peticiones pendientes de una comunidad, las más antiguas primero."""
        return (
            self.model.query.filter_by(community_id=community_id, status=CommunityDatasetRequest.STATUS_PENDING)
            .order_by(self.model.created_at.asc(), self.model.id.asc())
            .all()
        )

    def get_by_requester(self, user_id: int) -> list[CommunityDatasetRequest]:
        """Peticiones de un usuario, las más recientes primero."""
        return (
            self.model.query.filter_by(requester_id=user_id)
            .order_by(self.model.created_at.desc(), self.model.id.desc())
            .all()
        )

    def get_pending(self, community_id: int, dataset_id: int) -> CommunityDatasetRequest | None:
        """Petición pendiente de ese dataset en esa comunidad, si existe."""
        return self.model.query.filter_by(
            community_id=community_id,
            dataset_id=dataset_id,
            status=CommunityDatasetRequest.STATUS_PENDING,
        ).first()
