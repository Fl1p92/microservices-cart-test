"""Data migration. Add carts

Revision ID: 2560f7762880data
Revises: b13d1d3c6adb
Create Date: 2022-02-18 17:06:38.432854

"""
from alembic import op
from sqlalchemy.orm import sessionmaker

from cart.db.factories import CartFactory, CartItemFactory
from cart.db.models import Cart

# revision identifiers, used by Alembic.
revision = '2560f7762880data'
down_revision = 'b13d1d3c6adb'
branch_labels = None
depends_on = None


def upgrade():
    # Create carts and cart_items objects and add them to the list
    carts = [CartFactory(user_id=id_) for id_ in range(1, 5)]
    cart_items = [CartItemFactory(cart=cart) for cart in carts]
    # Add carts and cart_items to db
    with sessionmaker(bind=op.get_bind())() as session:
        with session.begin():
            session.add_all(carts + cart_items)


def downgrade():
    # Delete carts which was created by migration's `upgrade()`
    with sessionmaker(bind=op.get_bind())() as session:
        with session.begin():
            session.query(Cart).filter(Cart.user_id >= 1, Cart.user_id <= 4).delete()
