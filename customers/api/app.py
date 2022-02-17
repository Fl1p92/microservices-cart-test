import asyncio
import logging
from functools import partial
from types import AsyncGeneratorType, MappingProxyType
from typing import AsyncIterable, Mapping

from aiohttp import PAYLOAD_REGISTRY
from aiohttp.web_app import Application
from aiohttp_apispec import validation_middleware, AiohttpApiSpec
from aiohttp_jwt import JWTMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from customers import settings
from customers.api import API_VIEWS, JWT_WHITE_LIST
from customers.api.middleware import error_middleware
from customers.api.payloads import AsyncGenJSONListPayload, JsonPayload
from customers.rpc.server import GRPCServer
from customers.utils import is_jwt_token_revoked, fix_white_list_urls


log = logging.getLogger(__name__)
docs_path = '/api/v1/docs/'
jwt_middleware = JWTMiddleware(secret_or_pub_key=settings.JWT_SECRET,
                               whitelist=[f'{docs_path}.*'] + fix_white_list_urls(JWT_WHITE_LIST),
                               algorithms=settings.JWT_ALGORITHMS,
                               is_revoked=is_jwt_token_revoked)


async def setup_db(app: Application, pg_url: str | None = None):
    """
    Initiate connection to database on startup and close it on cleanup
    """
    log.info(f'Connecting to database: {settings.DB_INFO}')
    engine = create_async_engine(pg_url or settings.DB_URL, echo=settings.DEBUG)
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


async def setup_grpc_server(app: Application):
    """
    Initiate and start gRPC server on startup and stop it on cleanup
    """
    server = GRPCServer()
    grpc_task = asyncio.ensure_future(server.start())
    log.info('Started gRPC server.')

    try:
        yield

    finally:
        await server.stop()
        grpc_task.cancel()
        await grpc_task
        log.info('Stopped gRPC server.')


def create_app(pg_url: str | None = None) -> Application:
    """
    Creates an instance of the application, ready to run.
    """
    app = Application(middlewares=[error_middleware, jwt_middleware, validation_middleware])

    # Connect to postgres at start and disconnect at stop
    app.cleanup_ctx.append(partial(setup_db, pg_url=pg_url))

    # Start gRPC server at start and shutdown at stop
    app.cleanup_ctx.append(setup_grpc_server)

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
