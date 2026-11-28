from alembic import op
import sqlalchemy as sa

revision = '3b9e5d27c4f0'
down_revision = ('002', '002_songhub_datasets', 'daa40a343908')
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('user', sa.Column('role', sa.String(length=20), nullable=False, server_default='user'))

def downgrade():
    op.drop_column('user', 'role')
