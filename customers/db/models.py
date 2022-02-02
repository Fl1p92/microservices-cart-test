from passlib.hash import sha256_crypt
from sqlalchemy import Column, Integer, MetaData, String, DateTime, Boolean, select
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.sql.expression import text


# Default naming convention for all indexes and constraints
# See why this is important and how it would save your time:
# https://alembic.sqlalchemy.org/en/latest/naming.html
convention = {
    'all_column_names': lambda constraint, table: '_'.join([
        column.name for column in constraint.columns.values()
    ]),
    'ix': 'ix__%(table_name)s__%(all_column_names)s',
    'uq': 'uq__%(table_name)s__%(all_column_names)s',
    'ck': 'ck__%(table_name)s__%(constraint_name)s',
    'fk': 'fk__%(table_name)s__%(all_column_names)s__%(referred_table_name)s',
    'pk': 'pk__%(table_name)s'
}

# Registry for all tables
metadata = MetaData(naming_convention=convention)


@as_declarative(metadata=metadata)
class Base:
    """Base model class"""
    id = Column(Integer, primary_key=True)
    created = Column(DateTime(timezone=True), server_default=text('clock_timestamp()'), nullable=False)

    @declared_attr
    def __tablename__(cls):
        return f"{cls.__name__.lower()}s"

    def __repr__(self):
        return f"[{self.id}] {self.__class__.__name__}"


class User(Base):
    email = Column(String, nullable=False, unique=True)
    first_name = Column(String, nullable=False, default='')
    last_name = Column(String, nullable=False, default='')
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)

    @staticmethod
    def make_user_password_hash(raw_password: str) -> str:
        """
        Turn a plain-text password into a hash for database storage.
        """
        return sha256_crypt.hash(raw_password)

    @staticmethod
    def check_user_password(raw_password: str, hashed_password: str) -> bool:
        """
        Return a boolean of whether the raw_password was correct.
        """
        return sha256_crypt.verify(raw_password, hashed_password)


# Sql alchemy tables
users_t = User.__table__

# Queries preset
MAIN_USER_QUERY = (select([users_t.c.id, users_t.c.created, users_t.c.email,
                           users_t.c.first_name, users_t.c.last_name, users_t.c.is_admin])
                   .order_by(users_t.c.id))
