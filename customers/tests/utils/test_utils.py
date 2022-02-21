from datetime import datetime, timedelta
from http import HTTPStatus

from freezegun import freeze_time

from customers import settings
from customers.api import views, schema
from customers.db.factories import UserFactory
from customers.utils import url_for, fix_white_list_urls, get_jwt_token_for_user


async def test_jwt_token_revoke(authorized_api_client, db_session):
    api_client, _ = authorized_api_client
    admin_user = UserFactory(is_admin=True)
    await admin_user.async_save(db_session=db_session)
    assert admin_user.is_admin  # specifies admin user
    api_client._session.headers["Authorization"] = f'Bearer {get_jwt_token_for_user(user=admin_user)}'

    # Get all users with valid token
    response = await api_client.get(url_for(views.UsersListAPIView.URL_PATH))
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.UserListResponseSchema().validate(response_data)
    assert not errors

    # Attempt to get all users with revoked token
    future = datetime.utcnow() + settings.JWT_EXPIRATION_DELTA + timedelta(days=1)
    with freeze_time(future):
        response = await api_client.get(url_for(views.UsersListAPIView.URL_PATH))
        # Response checks
        assert response.status == HTTPStatus.UNAUTHORIZED
        assert response.content_type == 'application/json'
        # Response data checks
        response_data = await response.json()
        assert response_data['error']['message'] == '401: Invalid authorization token, Signature has expired'


async def test_fix_white_list_urls():

    test_urls = ['/api/v1/users/list/',
                 r'/api/v1/users/{user_id:\d+}/',
                 r'/api/v1/users/{user_id:\d+}/change-password/']

    fixed_urls = fix_white_list_urls(test_urls)
    assert fixed_urls[0] == test_urls[0]  # the same
    assert fixed_urls[1] == '/api/v1/users/.*/'
    assert fixed_urls[2] == '/api/v1/users/.*/change-password/'
