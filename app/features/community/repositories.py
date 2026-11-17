from splent_framework.repositories.BaseRepository import BaseRepository

from app.features.community.models import Community


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
