import logging
from argparse import Namespace
from collections.abc import AsyncIterable

from aiohttp.web_urldispatcher import DynamicResource
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from sqlalchemy.sql import Select


log = logging.getLogger(__name__)


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


def make_alembic_config(cmd_opts: Namespace) -> Config:
    """
    Creates alembic configuration object.
    """
    config = Config(file_=cmd_opts.config, ini_section=cmd_opts.name, cmd_opts=cmd_opts)
    config.set_main_option('script_location', 'db/alembic')
    if cmd_opts.pg_url:
        config.set_main_option('sqlalchemy.url', cmd_opts.pg_url)
    return config


def url_for(path: str, **kwargs) -> str:
    """
    Generates URL for dynamic aiohttp route with included.
    """
    kwargs = {
        key: str(value)  # All values must be str (for DynamicResource)
        for key, value in kwargs.items()
    }
    return str(DynamicResource(path).url_for(**kwargs))


async def add_objects_to_db(objects_list: list, db_session: AsyncSession) -> None:
    """
    Dirty hack to save objects to database via AsyncSession.
    """
    db_session.add_all(objects_list)
    await db_session.commit()
