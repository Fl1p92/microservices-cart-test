import asyncio
import uuid
from argparse import Namespace

import aiohttp
import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession as BaseAsyncSession
from sqlalchemy.orm import sessionmaker
from yarl import URL

from cart import settings
from cart.api.app import create_app
from cart.db.models import metadata
from cart.settings import DB_URL
from cart.utils import make_alembic_config


POSTGRES_DEFAULT_DB = "postgres"


async def create_database(url: str):
    """Issue the appropriate CREATE DATABASE statement.

    To create a database, you can pass a simple URL that would have
    been passed to `create_async_engine`.
    """
    url_object = make_url(url)
    database_name = url_object.database
    dbms_url = url_object.set(database=POSTGRES_DEFAULT_DB)
    engine = create_async_engine(dbms_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        c = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{database_name}'"))
        database_exists = c.scalar() == 1
    if database_exists:
        await drop_database(url_object)

    async with engine.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{database_name}" ENCODING "utf8" TEMPLATE template1'))
    await engine.dispose()


async def drop_database(url: str):
    """Issue the appropriate DROP DATABASE statement.

    Works similar to the `create_database` func in that both url text
    and a constructed url are accepted.
    """
    url_object = make_url(url)
    dbms_url = url_object.set(database=POSTGRES_DEFAULT_DB)
    engine = create_async_engine(dbms_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        disc_users = """
        SELECT pg_terminate_backend(pg_stat_activity.{pid_column})
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{database}'
          AND {pid_column} != pg_backend_pid();
        """.format(pid_column="pid", database=url_object.database)
        await conn.execute(text(disc_users))

        await conn.execute(text(f'DROP DATABASE "{url_object.database}"'))
    await engine.dispose()


@pytest.fixture(scope="module")
def event_loop() -> asyncio.AbstractEventLoop:
    """
    Creates an instance of the default event loop for the test session.
    """
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope="module")
async def postgres_url() -> str:
    """
    Creates a temporary database and yield db_url.
    """
    tmp_name = '.'.join([uuid.uuid4().hex, 'pytest'])
    db_url = str(URL(DB_URL).with_path(tmp_name))
    await create_database(db_url)
    try:
        yield db_url
    finally:
        await drop_database(db_url)


@pytest.fixture(scope="module")
def alembic_config(postgres_url: str) -> Config:
    """
    Creates a configuration object for alembic, configured for a temporary database.
    """
    cmd_options = Namespace(config='cart/alembic.ini', name='alembic', pg_url=postgres_url, raiseerr=False, x=None)
    return make_alembic_config(cmd_options)


@pytest.fixture(scope="module")
async def pg_engine(postgres_url: str) -> AsyncEngine:
    """
    Creates tables in db to run the test.
    Creates and returns an async database engine.
    """
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(pg_engine: AsyncEngine) -> BaseAsyncSession:
    """
    Returns the session with connection to the database.
    """
    AsyncSession = sessionmaker(bind=pg_engine, class_=BaseAsyncSession, expire_on_commit=False)
    session = AsyncSession()
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
async def authorized_api_client(db_session, aiohttp_client, aiomisc_unused_port: int, postgres_url: str, event_loop):
    """
    Returns API test client and JWT tokens for admin and non-admin from customers service.
    """
    async with aiohttp.ClientSession() as session:
        # Create user in customer service with is_admin = False
        user_create_url = f'http://{settings.CUSTOMERS_HOST}:{settings.CUSTOMERS_PORT}/api/v1/users/create/'
        email_passwd = f'cart_user{uuid.uuid4().hex}@email.com'
        user_data = {'email': email_passwd, 'password': email_passwd, 'is_admin': False}
        async with session.post(url=user_create_url, data=user_data) as response:
            response_data = await response.json()
            user_id = response_data['data']['id']
        # Login as non-admin user, get JWT token
        user_login_url = f'http://{settings.CUSTOMERS_HOST}:{settings.CUSTOMERS_PORT}/api/v1/auth/login/'
        async with session.post(url=user_login_url, data=user_data) as response:
            response_data = await response.json()
            non_admin_jwt_token = response_data['data']['token']
        # Set is_admin to True
        patch_data = {'is_admin': True}
        users_url = f'http://{settings.CUSTOMERS_HOST}:{settings.CUSTOMERS_PORT}/api/v1/users/{user_id}/'
        async with session.patch(url=users_url,
                                 data=patch_data,
                                 headers={'Authorization': non_admin_jwt_token}) as response:
            await response.json()
        # Login as admin user, get JWT token
        async with session.post(url=user_login_url, data=user_data) as response:
            response_data = await response.json()
            admin_jwt_token = response_data['data']['token']

    app = create_app(pg_url=postgres_url)
    client = await aiohttp_client(app, server_kwargs={'port': aiomisc_unused_port})
    try:
        yield client, non_admin_jwt_token, admin_jwt_token, user_id
    finally:
        # Delete created user
        async with aiohttp.ClientSession() as session:
            async with session.delete(url=users_url, headers={'Authorization': admin_jwt_token}) as response:
                await response.json()
        await client.close()
