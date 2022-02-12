from http import HTTPStatus

from aiohttp.web_exceptions import HTTPNotFound
from aiohttp.web_response import Response
from aiohttp.web_urldispatcher import View
from aiohttp_apispec import docs, request_schema, response_schema
from asyncpg import UniqueViolationError
from marshmallow import ValidationError
from sqlalchemy import select, text, exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from cart.api import schema
from cart.api.mixins import CheckObjectExistsMixin, GetSerializedCartInfoMixin
from cart.db.models import products_t, carts_t, cartitems_t
from cart.utils import get_inner_exception, SelectQuery


# swagger security schema
jwt_security = [{'JWT Authorization': []}]


class BaseView(View):
    URL_PATH: str

    @property
    def engine(self) -> AsyncEngine:
        return self.request.app['engine']


class ProductsListAPIView(BaseView):
    """
    Returns information for all products.
    """
    URL_PATH = '/api/v1/products/list/'

    @docs(tags=['products'],
          summary='List of products',
          description='Returns information for all products',
          parameters=[{
              'in': 'query',
              'name': 'search',
              'description': 'Search for a product by name'
          }])
    @response_schema(schema.ProductsListResponseSchema(), code=HTTPStatus.OK.value)
    async def get(self):
        products_query = select(products_t)
        if search_term := self.request.query.get('search'):
            products_query = products_query.where(products_t.c.name.ilike(f'%{search_term}%'))
        body = SelectQuery(query=products_query, transaction_ctx=self.engine.begin())
        return Response(body=body, status=HTTPStatus.OK)


class CartRetrieveDestroyAPIView(GetSerializedCartInfoMixin, BaseView):
    """
    Returns information about or clear user's cart.
    """
    URL_PATH = r'/api/v1/cart/{user_id:\d+}/'
    object_id_path = 'user_id'

    @property
    def object_id(self) -> int:
        return int(self.request.match_info.get(self.object_id_path))

    @docs(tags=['cart'],
          summary="Retrieve user's cart",
          description="Returns information about user's cart",
          security=jwt_security)
    @response_schema(schema.CartResponseSchema(), code=HTTPStatus.OK.value)
    async def get(self):
        # Check user's existing cart. If not - create a new one
        async with self.engine.begin() as conn:
            cart_exists_result = await conn.execute(select(exists().where(carts_t.c.user_id == self.object_id)))
            if not cart_exists_result.scalar():
                await conn.execute(carts_t.insert().values(user_id=self.object_id))
        # Get up-to-date information about user's cart
        response_data = await self.get_cart_response_data(user_id=self.object_id)
        return Response(body=schema.CartResponseSchema().dump({'data': response_data}),
                        status=HTTPStatus.OK)

    @docs(tags=['cart'],
          summary="Clean user's cart",
          description="Deletes all cart items from user's cart",
          security=jwt_security)
    @response_schema(schema.NoContentResponseSchema(), code=HTTPStatus.NO_CONTENT.value)
    async def delete(self):
        # Check user's existing cart. If not - raise HTTPNotFound
        async with self.engine.begin() as conn:
            cart_exists_result = await conn.execute(select(exists().where(carts_t.c.user_id == self.object_id)))
            if not cart_exists_result.scalar():
                raise HTTPNotFound()
            else:
                delete_query = cartitems_t.delete().where(cartitems_t.c.cart_id == self.object_id)
                await conn.execute(delete_query)
        return Response(body={}, status=HTTPStatus.NO_CONTENT)


class CartItemCreateAPIView(CheckObjectExistsMixin, GetSerializedCartInfoMixin, BaseView):
    """
    Creates cart item, returns, changes or deletes user's cart.
    """
    URL_PATH = r'/api/v1/cart-item/{cart_id:\d+}/create'
    object_id_path = 'cart_id'
    check_exists_column = carts_t.c.user_id

    @docs(tags=['cart-item'],
          summary='Create new cart item',
          description="Adds new cart item to user's cart",
          security=jwt_security)
    @request_schema(schema.CartItemSchema(only=['product_id', 'quantity']))
    @response_schema(schema.CartResponseSchema(), code=HTTPStatus.CREATED.value)
    async def post(self):
        # The transaction is required in order to roll back partially added changes in case of an error
        # (or disconnection of the client without waiting for a response).
        async with self.engine.begin() as conn:
            validated_data = self.request['validated_data']
            # Create cart item with a check for uniqueness
            try:
                await conn.execute(cartitems_t.insert().values(**validated_data, cart_id=self.object_id))
            except IntegrityError as err:
                if (inner_exc := get_inner_exception(err)) and isinstance(inner_exc, UniqueViolationError):
                    raise ValidationError({
                        "product_id": ["The product is already in cart. "
                                       "Please change the product or just update it's quantity."]
                    })
                else:  # pragma: no cover
                    raise ValidationError({'non_field_errors': ['Failed to add this product to cart.']})
        # Get up-to-date information about user's cart
        response_data = await self.get_cart_response_data(user_id=self.object_id)
        return Response(body=schema.CartResponseSchema().dump({'data': response_data}),
                        status=HTTPStatus.CREATED)


class CartItemUpdateDestroyAPIView(CheckObjectExistsMixin, GetSerializedCartInfoMixin, BaseView):
    """
    Updates quantity or deletes cart item from user's cart.
    """
    URL_PATH = r'/api/v1/cart-item/{item_id:\d+}/'
    object_id_path = 'item_id'
    check_exists_column = cartitems_t.c.id

    @docs(tags=['cart-item'],
          summary='Update cart item quantity',
          description="Updates cart item quantity in user's cart",
          security=jwt_security)
    @request_schema(schema.CartItemSchema(only=['quantity']))
    @response_schema(schema.CartResponseSchema(), code=HTTPStatus.OK.value)
    async def patch(self):
        async with self.engine.begin() as conn:
            validated_data = self.request['validated_data']
            # Blocking will avoid race conditions between concurrent update requests
            await conn.execute(text('SELECT pg_advisory_xact_lock(:lid)').bindparams(lid=self.object_id))
            # Update query
            patch_query = (cartitems_t.update()
                           .values(validated_data)
                           .where(cartitems_t.c.id == self.object_id)
                           .returning(cartitems_t.c.cart_id))
            cart_id_result = await conn.execute(patch_query)
            cart_id = cart_id_result.scalar()
        # Get up-to-date information about user's cart
        response_data = await self.get_cart_response_data(user_id=cart_id)
        return Response(body=schema.CartResponseSchema().dump({'data': response_data}),
                        status=HTTPStatus.OK)

    @docs(tags=['cart-item'],
          summary='Delete cart item',
          description="Deletes cart item from user's cart",
          security=jwt_security)
    @response_schema(schema.NoContentResponseSchema(), code=HTTPStatus.NO_CONTENT.value)
    async def delete(self):
        delete_query = cartitems_t.delete().where(cartitems_t.c.id == self.object_id)
        async with self.engine.begin() as conn:
            await conn.execute(delete_query)
        return Response(body={}, status=HTTPStatus.NO_CONTENT)
