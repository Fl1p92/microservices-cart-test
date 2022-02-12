from decimal import Decimal

import factory

from cart.db.models import Product, Cart, CartItem


class ProductFactory(factory.alchemy.SQLAlchemyModelFactory):

    class Meta:
        model = Product
        strategy = factory.BUILD_STRATEGY

    name = factory.Sequence(lambda n: f'Product_{n}')
    description = factory.Faker('sentence', nb_words=5)
    price = factory.Faker('random_element', elements=[Decimal(f'{x}.99') for x in (99, 149, 199, 249, 299)])


class CartFactory(factory.alchemy.SQLAlchemyModelFactory):

    class Meta:
        model = Cart
        strategy = factory.BUILD_STRATEGY

    user_id = factory.Faker('random_int')


class CartItemFactory(factory.alchemy.SQLAlchemyModelFactory):

    class Meta:
        model = CartItem
        strategy = factory.BUILD_STRATEGY

    cart = factory.SubFactory(CartFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = factory.Faker('random_int', min=1, max=5)
