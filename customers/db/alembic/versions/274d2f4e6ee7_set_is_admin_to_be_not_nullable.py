"""Set is_admin to be not nullable

Revision ID: 274d2f4e6ee7
Revises: 93cac78817da
Create Date: 2022-02-07 13:12:03.321080

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '274d2f4e6ee7'
down_revision = '93cac78817da'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'users',
        'is_admin',
        existing_type=sa.BOOLEAN(),
        nullable=False
    )


def downgrade():
    op.alter_column(
        'users',
        'is_admin',
        existing_type=sa.BOOLEAN(),
        nullable=True
    )
