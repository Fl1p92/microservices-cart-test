import logging
from collections.abc import AsyncIterable
from datetime import datetime

import jwt
from aiohttp.web_request import Request
from sqlalchemy import select, exists
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import Select

from customers import settings
from customers.api.schema import UserSchema
from customers.db.models import User, users_t


log = logging.getLogger(__name__)


def get_jwt_token_for_user(user: dict | Row | User) -> str:
    """
    Return a jwt token for a given user_data.
    """
    if isinstance(user, (User, Row)):
        user = UserSchema().dump(user)
    payload_data = {
        'id': user['id'],
        'email': user['email'],
        'is_admin': user['is_admin'],
        'exp': datetime.utcnow() + settings.JWT_EXPIRATION_DELTA
    }
    token = jwt.encode(payload=payload_data, key=settings.JWT_SECRET)
    return token


async def is_jwt_token_revoked(request: Request, decoded: dict) -> bool:
    """
    Checks if the user id from the decoded token exists.
    """
    user_id = decoded['id']
    query = select(exists().where(users_t.c.id == user_id))
    async with request.app['engine'].connect() as conn:
        result = await conn.execute(query)
    return not result.scalar()


class SelectQuery(AsyncIterable):
    """
    Used to send data from PostgreSQL to client immediately after receiving,
    without buffering all the data using server side cursor.
    """

    __slots__ = ('query', 'transaction_ctx')

    def __init__(self, query: Select, transaction_ctx: AsyncConnection):
        self.query = query
        self.transaction_ctx = transaction_ctx

    async def __aiter__(self):
        async with self.transaction_ctx as conn:
            cursor = await conn.stream(self.query)
            async for row in cursor:
                yield row


def get_inner_exception(outer_exception: Exception) -> Exception:
    """
    Get inner exception from the chained exceptions.
    """
    inner_exc = True
    while inner_exc:
        if inner_exc := getattr(outer_exception, '__cause__', None):
            outer_exception = inner_exc
    return outer_exception
