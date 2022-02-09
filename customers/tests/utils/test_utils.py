from datetime import datetime, timedelta
from http import HTTPStatus

from freezegun import freeze_time

from customers import settings
from customers.api import views, schema
from customers.utils import url_for


async def test_jwt_token_revoke(authorized_api_client, db_session):
    api_client, user = authorized_api_client

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
