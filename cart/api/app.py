import logging
from functools import partial
from types import AsyncGeneratorType, MappingProxyType
from typing import AsyncIterable, Mapping

from aiohttp import PAYLOAD_REGISTRY
from aiohttp.web_app import Application
from aiohttp_apispec import validation_middleware, AiohttpApiSpec
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from cart import settings
from cart.api import API_VIEWS
from cart.api.middleware import error_middleware, grpc_jwt_middleware
from cart.api.payloads import AsyncGenJSONListPayload, JsonPayload


log = logging.getLogger(__name__)


async def setup_db(app: Application, pg_url: str | None = None):
    """
    Initiate connection to database on startup and close it on cleanup
    """
    log.info(f'Connecting to database: {settings.DB_INFO}')
    engine = create_async_engine(pg_url or settings.DB_URL, echo=True)
    async with engine.connect() as conn:
        await conn.execute(text('Select 1;'))
    app['engine'] = engine
    log.info(f'Connected to database: {settings.DB_INFO}')

    try:
        yield

    finally:
        log.info(f'Disconnecting from database: {settings.DB_INFO}')
        await app['engine'].dispose()
        log.info(f'Disconnected from database: {settings.DB_INFO}')


def create_app(pg_url: str | None = None) -> Application:
    """
    Creates an instance of the application, ready to run.
    """
    app = Application(middlewares=[error_middleware, grpc_jwt_middleware, validation_middleware])

    # Connect to postgres at start and disconnect at stop
    app.cleanup_ctx.append(partial(setup_db, pg_url=pg_url))

    # Registering views
    for view in API_VIEWS:
        log.debug(f'Registering view {view} as {view.URL_PATH}')
        app.router.add_route('*', view.URL_PATH, view)

    # Swagger documentation
    api_spec = AiohttpApiSpec(app=app, title='Cart Service API', version='v1', request_data_name='validated_data',
                              swagger_path=settings.DOCS_PATH, url=f'{settings.DOCS_PATH}swagger.json',
                              static_path=f'{settings.DOCS_PATH}static')
    # Manual add Authorize header to swagger
    api_key_scheme = {"type": "apiKey", "in": "header", "name": "Authorization"}
    api_spec.spec.components.security_scheme('JWT Authorization', api_key_scheme)

    # Automatic json serialization of data in HTTP responses
    PAYLOAD_REGISTRY.register(AsyncGenJSONListPayload, (AsyncGeneratorType, AsyncIterable))
    PAYLOAD_REGISTRY.register(JsonPayload, (Mapping, MappingProxyType))

    return app
