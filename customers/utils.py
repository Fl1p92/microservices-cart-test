import logging
from collections.abc import AsyncIterable
from datetime import datetime

import jwt
from asyncpg import Record
from asyncpgsa.transactionmanager import ConnectionTransactionContextManager
from sqlalchemy.sql import Select

from customers import settings
from customers.api.schema import UserSchema
from customers.db.models import User


log = logging.getLogger(__name__)


def get_jwt_token_for_user(user: dict | Record | User) -> str:
    """
    Return a jwt token for a given user_data.
    """
    if isinstance(user, User):
        user = UserSchema().dump(user)
    payload_data = {
        'id': user['id'],
        'email': user['email'],
        'is_admin': user['is_admin'],
        'exp': datetime.utcnow() + settings.JWT_EXPIRATION_DELTA
    }
    token = jwt.encode(payload=payload_data, key=settings.JWT_SECRET)
    return token


class SelectQuery(AsyncIterable):
    """
    Used to send data from PostgreSQL to client immediately after receiving,
    in parts, without buffering all the data.
    """
    PREFETCH = 1000

    __slots__ = ('query', 'transaction_ctx', 'prefetch', 'timeout')

    def __init__(self, query: Select,
                 transaction_ctx: ConnectionTransactionContextManager,
                 prefetch: int = None,
                 timeout: float = None):
        self.query = query
        self.transaction_ctx = transaction_ctx
        self.prefetch = prefetch or self.PREFETCH
        self.timeout = timeout

    async def __aiter__(self):
        async with self.transaction_ctx as conn:
            cursor = conn.cursor(self.query, prefetch=self.prefetch, timeout=self.timeout)
            async for row in cursor:
                yield row
