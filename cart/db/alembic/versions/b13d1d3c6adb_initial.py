"""Initial

Revision ID: b13d1d3c6adb
Revises: 
Create Date: 2022-02-10 18:23:12.433949

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b13d1d3c6adb'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'carts',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('user_id', name=op.f('pk__carts'))
    )
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('price', sa.Numeric(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk__products'))
    )
    op.create_table(
        'cartitems',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
        sa.Column('cart_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(['cart_id'], ['carts.user_id'], name=op.f('fk__cartitems__cart_id__carts'),
                                onupdate='CASCADE', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk__cartitems__product_id__products'),
                                onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk__cartitems')),
        sa.UniqueConstraint('cart_id', 'product_id', name=op.f('uq__cartitems__cart_id_product_id'))
    )


def downgrade():
    op.drop_table('cartitems')
    op.drop_table('products')
    op.drop_table('carts')
