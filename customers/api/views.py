from http import HTTPStatus

from aiohttp import hdrs
from aiohttp.web_response import Response
from aiohttp.web_urldispatcher import View
from aiohttp_apispec import docs, request_schema, response_schema
from asyncpg import UniqueViolationError
from asyncpgsa import PG
from marshmallow import ValidationError

from customers.api import schema, mixins
from customers.api.permissions import IsAuthenticatedForObject
from customers.db.models import User, users_t, MAIN_USER_QUERY
from customers.utils import SelectQuery, get_jwt_token_for_user


# swagger security schema
jwt_security = [{'JWT Authorization': []}]


class BaseView(View):
    URL_PATH: str

    @property
    def pg(self) -> PG:
        return self.request.app['pg']


class LoginAPIView(BaseView):
    """
    Checks the credentials and return the JWT Token if the credentials are valid and authenticated.
    """
    URL_PATH = '/api/v1/auth/login/'

    @docs(tags=['auth'],
          summary='Login',
          description='Login user to system')
    @request_schema(schema.UserSchema(only=('email', 'password')))
    @response_schema(schema.JWTTokenResponseSchema(), code=HTTPStatus.OK.value)
    async def post(self):
        validated_data = self.request['validated_data']
        get_user_query = MAIN_USER_QUERY.where(users_t.c.email == validated_data['email'])
        user = await self.pg.fetchrow(get_user_query)
        if user is not None:
            if User.check_user_password(validated_data['password'], user['password']):
                token = get_jwt_token_for_user(user=user)
                response_data = {
                    'token': f'Bearer {token}',
                    'user': schema.UserSchema(only=['id', 'email']).dump(user)
                }
                return Response(body={'data': response_data}, status=HTTPStatus.OK)
        raise ValidationError({'non_field_errors': ['Unable to log in with provided credentials.']})


class UserCreateAPIView(BaseView):
    """
    Creates new user.
    """
    URL_PATH = '/api/v1/users/create/'

    @docs(tags=['users'],
          summary='Create new user',
          description='Add new user to database')
    @request_schema(schema.UserSchema(exclude=('id', 'created')))
    @response_schema(schema.UserDetailsResponseSchema(), code=HTTPStatus.CREATED.value)
    async def post(self):
        # The transaction is required in order to roll back partially added changes in case of an error
        # (or disconnection of the client without waiting for a response).
        async with self.pg.transaction() as conn:
            validated_data = self.request['validated_data']
            validated_data['password'] = User.make_user_password_hash(validated_data['password'])
            insert_user_query = users_t.insert().returning(MAIN_USER_QUERY).values(validated_data)
            try:
                new_user = await conn.fetchrow(insert_user_query)
            except UniqueViolationError as err:
                field = err.constraint_name.split('__')[-1]
                raise ValidationError({f"{field}": [f"User with this {field} already exists."]})
        return Response(body={'data': new_user}, status=HTTPStatus.CREATED)


class UsersListAPIView(BaseView):
    """
    Returns information for all users.
    """
    URL_PATH = '/api/v1/users/list/'

    @docs(tags=['users'],
          summary='List of users',
          description='Returns information for all users',
          security=jwt_security,
          parameters=[{
              'in': 'query',
              'name': 'search',
              'description': 'Search for a user by id or email'
          }])
    @response_schema(schema.UserListResponseSchema(), code=HTTPStatus.OK.value)
    async def get(self):
        users_query = MAIN_USER_QUERY
        if search_term := self.request.query.get('search'):
            try:
                search_term = int(search_term)
            except ValueError:
                users_query = users_query.where(users_t.c.email.ilike(f'%{search_term}%'))
            else:
                users_query = users_query.where(users_t.c.id == search_term)
        body = SelectQuery(query=users_query, transaction_ctx=self.pg.transaction())
        return Response(body=body, status=HTTPStatus.OK)


class UserRetrieveUpdateDestroyAPIView(mixins.CheckObjectExistsMixin, mixins.CheckUserPermissionMixin, BaseView):
    """
    Returns, changes or delete information for a user.
    """
    URL_PATH = r'/api/v1/users/{user_id:\d+}/'
    object_id_path = 'user_id'
    check_exists_table = users_t
    skip_methods = [hdrs.METH_GET]
    permissions_classes = [IsAuthenticatedForObject]

    async def get_user(self):
        user_query = MAIN_USER_QUERY.where(users_t.c.id == self.object_id)
        user = await self.pg.fetchrow(user_query)
        return user

    @docs(tags=['users'],
          summary='Retrieve user',
          description='Returns information for a user',
          security=jwt_security)
    @response_schema(schema.UserDetailsResponseSchema(), code=HTTPStatus.OK.value)
    async def get(self):
        user = await self.get_user()
        return Response(body={'data': user}, status=HTTPStatus.OK)

    @docs(tags=['users'],
          summary='Update user',
          description='Updates information for a user',
          security=jwt_security)
    @request_schema(schema.UserPatchSchema())
    @response_schema(schema.UserDetailsResponseSchema(), code=HTTPStatus.OK.value)
    async def patch(self):
        async with self.pg.transaction() as conn:
            validated_data = self.request['validated_data']

            # Blocking will avoid race conditions between concurrent user change requests
            await conn.fetch('SELECT pg_advisory_xact_lock($1)', self.object_id)

            patch_query = users_t.update().values(validated_data).where(users_t.c.id == self.object_id)
            try:
                await conn.fetch(patch_query)
            except UniqueViolationError as err:
                field = err.constraint_name.split('__')[-1]
                raise ValidationError({f"{field}": [f"User with this {field} already exists."]})

        # Get up-to-date information about the user
        user = await self.get_user()
        return Response(body={'data': user}, status=HTTPStatus.OK)

    @docs(tags=['users'],
          summary='Delete user',
          description='Deletes information for a user',
          security=jwt_security)
    @response_schema(schema.NoContentResponseSchema(), code=HTTPStatus.NO_CONTENT.value)
    async def delete(self):
        delete_query = users_t.delete().where(users_t.c.id == self.object_id)
        await self.pg.fetch(delete_query)
        return Response(body={}, status=HTTPStatus.NO_CONTENT)


class UserChangePasswordAPIView(mixins.CheckObjectExistsMixin, mixins.CheckUserPermissionMixin, BaseView):
    """
    Change user's password.
    """
    URL_PATH = r'/api/v1/users/{user_id:\d+}/change-password/'
    object_id_path = 'user_id'
    check_exists_table = users_t
    permissions_classes = [IsAuthenticatedForObject]

    @docs(tags=['users'],
          summary='Change password',
          description='Set new password for a user',
          security=jwt_security)
    @request_schema(schema.UserChangePasswordSchema())
    @response_schema(schema.NoContentResponseSchema(), code=HTTPStatus.OK.value)
    async def patch(self):
        async with self.pg.transaction() as conn:
            validated_data = self.request['validated_data']
            new_password_hash = User.make_user_password_hash(validated_data['new_password'])

            # Blocking will avoid race conditions between concurrent user change requests
            await conn.fetch('SELECT pg_advisory_xact_lock($1)', self.object_id)

            patch_query = users_t.update().values(password=new_password_hash).where(users_t.c.id == self.object_id)
            await conn.fetch(patch_query)
        return Response(body={}, status=HTTPStatus.OK)
