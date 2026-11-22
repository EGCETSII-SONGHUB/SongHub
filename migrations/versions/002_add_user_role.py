from alembic import op 
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade(): 
    op.add_column('user', sa.Column('role', sa.String(length=20), nullable=False, server_default='user'))

def downgrade(): 
    op.drop_colum('user', 'role')