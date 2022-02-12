from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, Numeric, SmallInteger, String, Text, \
    UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.orm import relationship
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

    @declared_attr
    def __tablename__(cls):
        return f"{cls.__name__.lower()}s"

    def __repr__(self):
        return f"[{self.id}] {self.__class__.__name__}"

    async def async_save(self, db_session: AsyncSession):
        """
        Save current object to database via AsyncSession.
        """
        from cart.utils import add_objects_to_db  # to avoid circular imports

        await add_objects_to_db(objects_list=[self], db_session=db_session)


class BaseIdCreated(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True)
    created = Column(DateTime(timezone=True), server_default=text('clock_timestamp()'), nullable=False)


class Product(BaseIdCreated):
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Numeric, nullable=False)
    cart_items = relationship('CartItem', back_populates='product')


class Cart(Base):
    user_id = Column(Integer, primary_key=True)
    cart_items = relationship('CartItem', back_populates='cart')

    def __repr__(self):
        return f"[{self.user_id}] {self.__class__.__name__}"


class CartItem(BaseIdCreated):
    cart_id = Column(Integer, ForeignKey('carts.user_id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    cart = relationship('Cart', back_populates='cart_items')
    product_id = Column(Integer, ForeignKey('products.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    product = relationship('Product', back_populates='cart_items')
    quantity = Column(SmallInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint('cart_id', 'product_id'),
    )


# Sql alchemy tables
products_t = Product.__table__
carts_t = Cart.__table__
cartitems_t = CartItem.__table__
