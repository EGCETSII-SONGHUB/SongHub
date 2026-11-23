from datetime import datetime, timezone

from flask import url_for

from app import db

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
        "BaseDataset",
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
