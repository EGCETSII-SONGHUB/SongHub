from datetime import datetime, timezone

from flask import url_for

from app import db
from app.features.dataset.models import DataSet  # noqa: F401

community_curators = db.Table(
    "community_curators",
    db.Column("community_id", db.Integer, db.ForeignKey("community.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
)

community_datasets = db.Table(
    "community_datasets",
    db.Column("community_id", db.Integer, db.ForeignKey("community.id"), primary_key=True),
    db.Column("dataset_id", db.Integer, db.ForeignKey("data_set.id"), primary_key=True),
    db.Column("added_at", db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)),
)


class Community(db.Model):
    """Thematic or institutional space grouping related datasets under a shared umbrella."""

    __tablename__ = "community"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    logo = db.Column(db.String(256), nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    creator = db.relationship("User", foreign_keys=[creator_id], backref=db.backref("created_communities", lazy=True))
    curators = db.relationship(
        "User",
        secondary=community_curators,
        backref=db.backref("curated_communities", lazy=True),
        lazy="selectin",
    )
    datasets = db.relationship(
        "DataSet",
        secondary=community_datasets,
        backref=db.backref("communities", lazy=True),
        lazy=True,
    )

    def is_curator(self, user) -> bool:
        """Return True when *user* is an authenticated curator of this community."""
        if not user or not getattr(user, "is_authenticated", True):
            return False
        user_id = getattr(user, "id", None)
        return user_id is not None and any(curator.id == user_id for curator in self.curators)

    def get_logo_url(self) -> str | None:
        """Resolve the display URL for the community logo, or None if unset."""
        if not self.logo:
            return None
        if self.logo.startswith(("http://", "https://", "/")):
            return self.logo
        return url_for("community.serve_logo", filename=self.logo)

    def to_dict(self) -> dict:
        """Serialize the community and its associations into JSON-friendly primitives."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "logo": self.logo,
            "creator_id": self.creator_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "curators": [curator.id for curator in self.curators],
            "datasets": [dataset.id for dataset in self.datasets],
        }

    def __repr__(self) -> str:
        return f"Community<{self.id}: {self.name}>"


class CommunityDatasetRequest(db.Model):
    """A request from a user to add one of their datasets into a community"""

    __tablename__ = "community_dataset_request"

    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("community.id"), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    dataset_id = db.Column(db.Integer, db.ForeignKey("data_set.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    comment = db.Column(db.Text, nullable=True)  # comentario opcional
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    community = db.relationship(
        "Community",
        backref=db.backref("dataset_requests", lazy=True, cascade="all, delete-orphan"),
    )
    dataset = db.relationship("DataSet", backref=db.backref("community_requests", lazy=True))
    requester = db.relationship(
        "User", foreign_keys=[requester_id], backref=db.backref("community_dataset_requests", lazy=True)
    )
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_id])

    def is_pending(self) -> bool:
        return self.status == self.STATUS_PENDING

    def resolve(self, status: str, curator, comment: str | None = None) -> None:
        """Mark the request as accepted or rejected. Does not commit"""
        self.status = status
        self.resolved_by_id = curator.id
        self.resolved_at = datetime.now(timezone.utc)
        self.comment = (comment or "").strip() or None

    def __repr__(self) -> str:
        return (
            f"CommunityDatasetRequest<{self.id}: community={self.community_id}, "
            f"dataset={self.dataset_id} {self.status}>"
        )
