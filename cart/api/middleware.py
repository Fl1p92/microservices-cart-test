import json
import logging
import re
from http import HTTPStatus
from typing import Mapping

import grpc
from aiohttp import web
from aiohttp.web_exceptions import HTTPException
from aiohttp.web_middlewares import middleware
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from marshmallow import ValidationError

from cart import settings
from cart.api import JWT_WHITE_LIST
from cart.api.payloads import JsonPayload
from cart.utils import fix_white_list_urls
from protobufs.auth_pb2 import AuthRequest, JwtToken
from protobufs.auth_pb2_grpc import UserAuthStub

log = logging.getLogger(__name__)
VALIDATION_ERROR_DESCRIPTION = 'Request validation has failed'


def format_http_error(message: str | None = '', status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
                      fields: Mapping | None = None) -> Response:
    """
    Formats the error as an HTTP exception
    """
    status = HTTPStatus(status_code)
    error = {'code': status.name.lower()}

    # Adds field errors which failed marshmallow validation
    if '{' in message:
        error['message'] = VALIDATION_ERROR_DESCRIPTION
        error['fields'] = json.loads(message)
    # Other errors
    else:
        error['message'] = message or status.description

    # Adds field errors which failed validation in views
    if fields:
        error['fields'] = fields

    return Response(body={'error': error}, status=status_code)


def handle_validation_error(error: ValidationError):
    """
    Represents a data validation error as an HTTP response.
    """
    return format_http_error(message=VALIDATION_ERROR_DESCRIPTION, status_code=HTTPStatus.BAD_REQUEST,
                             fields=error.messages)


@middleware
async def error_middleware(request: Request, handler):
    try:
        return await handler(request)
    except HTTPException as err:
        # Exceptions that are HTTP responses were deliberately thrown for display to the client.
        # Text exceptions (or exceptions without information) are formatted in JSON
        if not isinstance(err.text, JsonPayload):
            return format_http_error(err.text, err.status_code)
        raise  # pragma: no cover

    except ValidationError as err:
        # Checking for errors in views
        return handle_validation_error(err)

    except Exception:  # pragma: no cover
        # All other exceptions cannot be displayed to the client as an HTTP response
        # and may inadvertently reveal internal information.
        log.exception('Unhandled exception')
        return format_http_error()


def check_request_in_whitelist(request: Request, whitelist_urls: list[str]) -> bool:
    """
    Checks if the requested view is from a whitelist.
    """
    for pattern in whitelist_urls:
        if re.match(pattern, request.path):
            return True
    return False


@middleware
async def grpc_jwt_middleware(request: Request, handler):
    """
    Middleware to validate user's jwt token via gRPC request.
    """
    # Skip middleware if requested view in whitelist
    whitelist = [f'{settings.DOCS_PATH}.*'] + fix_white_list_urls(JWT_WHITE_LIST)
    if check_request_in_whitelist(request, whitelist):
        return await handler(request)
    # Raise error if request doesn't have `Authorization` header
    if not (jwt_token := request.headers.get('Authorization')):
        raise web.HTTPForbidden(reason='Invalid authorization header')
    # Create gRPC objects and get gRPC response using secure channel
    with open('client.key', 'rb') as file:
        client_key = file.read()
    with open('client.pem', 'rb') as file:
        client_cert = file.read()
    with open('ca.pem', 'rb') as file:
        ca_cert = file.read()
    creds = grpc.ssl_channel_credentials(ca_cert, client_key, client_cert)
    grpc_client = UserAuthStub(grpc.secure_channel(f'{settings.GRPC_HOST}:{settings.GRPC_PORT}', creds))
    grpc_request = AuthRequest(token=JwtToken(value=jwt_token))
    try:
        grpc_response = grpc_client.ValidateToken(grpc_request)
    except grpc.RpcError as err:
        raise web.HTTPForbidden(reason=err.details())  # noqa
    # Set data from gRPC response to request
    request['payload'] = {'user_id': grpc_response.payload.user_id, 'is_admin': grpc_response.payload.is_admin}
    return await handler(request)
