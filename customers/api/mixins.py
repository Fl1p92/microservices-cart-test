from typing import NoReturn

from aiohttp.web_exceptions import HTTPNotFound, HTTPForbidden
from aiohttp.web_response import StreamResponse

from sqlalchemy import exists, select, Table


class CheckObjectExistsMixin:
    object_id_path: str
    check_exists_table: Table

    async def _iter(self) -> StreamResponse:
        await self.check_object_exists()
        return await super()._iter()

    @property
    def object_id(self) -> int:
        return int(self.request.match_info.get(self.object_id_path))

    async def check_object_exists(self) -> NoReturn:
        query = select(exists().where(self.check_exists_table.c.id == self.object_id))
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
