"""Add polymorphic dataset types and SongHub metadata.

Revision ID: 002_songhub_datasets
Revises: 7c65000861a1
"""

from alembic import op
import sqlalchemy as sa

revision = "002_songhub_datasets"
down_revision = "7c65000861a1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("data_set", sa.Column("dataset_type", sa.String(length=32), nullable=True))
    op.execute("UPDATE data_set SET dataset_type = 'uvl' WHERE dataset_type IS NULL")
    op.alter_column(
        "data_set",
        "dataset_type",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default="uvl",
    )
    op.create_index("ix_data_set_dataset_type", "data_set", ["dataset_type"])

    op.create_table(
        "song_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number_of_songs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("number_of_artists", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_streams", sa.Float(), nullable=True),
        sa.Column("average_views", sa.Float(), nullable=True),
        sa.Column("average_likes", sa.Float(), nullable=True),
    )
    op.create_table(
        "song_metadata",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("csv_filename", sa.String(length=255), nullable=False),
        sa.Column("columns", sa.Text(), nullable=False),
        sa.Column("song_metrics_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["song_metrics_id"], ["song_metrics.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "song_dataset",
        sa.Column("id", sa.Integer(), sa.ForeignKey("data_set.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("song_metadata_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["song_metadata_id"], ["song_metadata.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "song_file",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("checksum", sa.String(length=120), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["data_set.id"], ondelete="CASCADE"),
    )


def downgrade():
    op.drop_table("song_file")
    op.drop_table("song_dataset")
    op.drop_table("song_metadata")
    op.drop_table("song_metrics")
    op.drop_index("ix_data_set_dataset_type", table_name="data_set")
    op.drop_column("data_set", "dataset_type")
