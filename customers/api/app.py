import logging
from functools import partial
from types import AsyncGeneratorType, MappingProxyType
from typing import AsyncIterable, Mapping

from aiohttp import PAYLOAD_REGISTRY
from aiohttp.web_app import Application
from aiohttp_apispec import validation_middleware, AiohttpApiSpec
from aiohttp_jwt import JWTMiddleware
from asyncpgsa import PG

from customers import settings
from customers.api import API_VIEWS, JWT_WHITE_LIST
from customers.api.middleware import error_middleware
from customers.api.payloads import AsyncGenJSONListPayload, JsonPayload


log = logging.getLogger(__name__)
docs_path = '/api/v1/docs/'
jwt_middleware = JWTMiddleware(secret_or_pub_key=settings.JWT_SECRET,
                               whitelist=(f'{docs_path}.*') + JWT_WHITE_LIST,
                               algorithms=["HS256"])


async def setup_pg(app: Application, pg_url: str | None = None) -> PG:
    """
    Initiate connection to database on startup and close it on cleanup
    """
    log.info(f'Connecting to database: {settings.DB_INFO}')

    app['pg'] = PG()
    await app['pg'].init(pg_url or settings.DB_URL)
    await app['pg'].fetchval('SELECT 1')
    log.info(f'Connected to database: {settings.DB_INFO}')

    try:
        yield

    finally:
        log.info(f'Disconnecting from database: {settings.DB_INFO}')
        await app['pg'].pool.close()
        log.info(f'Disconnected from database: {settings.DB_INFO}')


def create_app(pg_url: str | None = None) -> Application:
    """
    Creates an instance of the application, ready to run.
    """
    app = Application(
        middlewares=[error_middleware, jwt_middleware, validation_middleware]
    )

    # Connect at start to postgres and disconnect at stop
    app.cleanup_ctx.append(partial(setup_pg, pg_url=pg_url))

    # Registering views
    for view in API_VIEWS:
        log.debug(f'Registering view {view} as {view.URL_PATH}')
        app.router.add_route('*', view.URL_PATH, view)

    # Swagger documentation
    api_spec = AiohttpApiSpec(app=app, title='Customers Service API', version='v1', request_data_name='validated_data',
                              swagger_path=docs_path, url=f'{docs_path}swagger.json', static_path=f'{docs_path}static')
    # Manual add Authorize header to swagger
    api_key_scheme = {"type": "apiKey", "in": "header", "name": "Authorization"}
    api_spec.spec.components.security_scheme('JWT Authorization', api_key_scheme)

    # Automatic json serialization of data in HTTP responses
    PAYLOAD_REGISTRY.register(AsyncGenJSONListPayload, (AsyncGeneratorType, AsyncIterable))
    PAYLOAD_REGISTRY.register(JsonPayload, (Mapping, MappingProxyType))

    return app
