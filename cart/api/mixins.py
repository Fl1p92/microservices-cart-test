from decimal import Decimal
from typing import NoReturn

from aiohttp.web_exceptions import HTTPNotFound, HTTPForbidden
from aiohttp.web_response import StreamResponse

from sqlalchemy import exists, select, Column, func

from cart.db.models import cartitems_t, products_t


class CheckObjectExistsMixin:
    object_id_path: str
    check_exists_column: Column

    async def _iter(self) -> StreamResponse:
        await self.check_object_exists()
        return await super()._iter()

    @property
    def object_id(self) -> int:
        return int(self.request.match_info.get(self.object_id_path))

    async def check_object_exists(self) -> NoReturn:
        query = select(exists().where(self.check_exists_column == self.object_id))
        async with self.engine.connect() as conn:
            result = await conn.execute(query)
        if not result.scalar():
            raise HTTPNotFound()


class CheckUserPermissionMixin:
    skip_methods: list = []
    permissions_classes: list = []

    async def _iter(self) -> StreamResponse:
        if self.request.method not in self.skip_methods:
            await self.check_permissions()
        return await super()._iter()

    async def check_permissions(self) -> NoReturn:
        permissions_objects = [permission() for permission in self.permissions_classes]
        for permission in permissions_objects:
            if not permission.has_permission(self.request, self):
                raise HTTPForbidden(reason='You do not have permission to perform this action.')


class GetSerializedCartInfoMixin:

    async def get_cart_response_data(self, user_id: int) -> dict:
        cart_items_query = select(cartitems_t).where(cartitems_t.c.cart_id == user_id)
        cart_total_price_query = (select(func.sum(cartitems_t.c.quantity * products_t.c.price))
                                  .join(products_t)
                                  .where(cartitems_t.c.cart_id == user_id))
        async with self.engine.connect() as conn:
            cart_items_result = await conn.execute(cart_items_query)
            cart_total_price_result = await conn.execute(cart_total_price_query)
        cart_items = cart_items_result.all()
        cart_total_price = cart_total_price_result.scalar() or Decimal('0.00')
        return {'user_id': user_id, 'total_price': cart_total_price, 'cart_items': cart_items}
