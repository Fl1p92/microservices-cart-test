"""Data migration. Add users

Revision ID: ed7855b80d3fdata
Revises: 274d2f4e6ee7
Create Date: 2022-02-18 16:04:49.514623

"""
from alembic import op
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from customers.db.factories import UserFactory
from customers.db.models import User


# revision identifiers, used by Alembic.
revision = 'ed7855b80d3fdata'
down_revision = '274d2f4e6ee7'
branch_labels = None
depends_on = None

ADMIN_EMAILS = ['admin1@email.com', 'admin2@email.com']
NON_ADMIN_EMAILS = ['nonadmin3@email.com', 'nonadmin4@email.com']


def upgrade():
    # Create users objects and add them to the list
    users_list = []
    users_list.extend(
        (UserFactory(id=id_, email=email, is_admin=True) for id_, email in enumerate(ADMIN_EMAILS, start=1))
    )
    users_list.extend(
        (UserFactory(id=id_, email=email) for id_, email in enumerate(NON_ADMIN_EMAILS, start=3))
    )
    # Add users from list to db
    with sessionmaker(bind=op.get_bind())() as session:
        with session.begin():
            session.add_all(users_list)
            session.execute(text('ALTER SEQUENCE users_id_seq RESTART WITH 5;'))


def downgrade():
    # Delete users who was created by migration's `upgrade()`
    with sessionmaker(bind=op.get_bind())() as session:
        with session.begin():
            session.query(User).filter(User.id >= 1, User.id <= 4).delete()
