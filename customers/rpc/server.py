import logging

import grpc
import jwt
from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import create_async_engine

from customers import settings
from customers.db.models import users_t
from protobufs.auth_pb2 import Payload, AuthRequest, AuthResponse
from protobufs.auth_pb2_grpc import UserAuthServicer, add_UserAuthServicer_to_server


log = logging.getLogger(__name__)


class UserAuthService(UserAuthServicer):
    """
    gRPC user auth service, which check user's jwt token.
    """

    async def ValidateToken(self, request: AuthRequest, context):
        payload = None
        try:
            scheme, token = request.token.value.strip().split(' ')
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Invalid JWT token')
        else:
            if scheme != 'Bearer':
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Invalid token scheme')
            if token:
                token = token.encode()
                try:
                    decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=settings.JWT_ALGORITHMS)
                except jwt.InvalidTokenError as exc:
                    log.exception(exc, exc_info=exc)
                    msg = f'Invalid authorization token, {exc}'
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, msg)
                else:
                    user_id = decoded['id']
                    query = select(exists().where(users_t.c.id == user_id))
                    engine = create_async_engine(settings.DB_URL)
                    async with engine.connect() as conn:
                        result = await conn.execute(query)
                    if not result.scalar():
                        await context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Token is revoked')
                    payload = Payload(user_id=user_id, email=decoded['email'], is_admin=decoded['is_admin'])

        return AuthResponse(payload=payload)


class GRPCServer:
    """
    Creates gRPC server, bind it to port and start/stop it.
    """

    def __init__(self):
        grpc.aio.init_grpc_aio()
        self.server = grpc.aio.server()
        add_UserAuthServicer_to_server(UserAuthService(), self.server)
        self.server.add_insecure_port(f"[::]:{settings.GRPC_PORT}")

    async def start(self):
        await self.server.start()
        await self.server.wait_for_termination()

    async def stop(self):
        await self.server.stop(0)
