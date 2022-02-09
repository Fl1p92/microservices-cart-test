from http import HTTPStatus

from aiohttp import ClientResponse
from sqlalchemy import select, func, desc, exists

from customers.db.factories import USER_TEST_PASSWORD, UserFactory
from customers.db.models import User
from customers.api import views, schema
from customers.utils import url_for, add_objects_to_db, get_jwt_token_for_user


ADDITIONAL_OBJECTS_QUANTITY = 5


async def check_response_for_objects_exists(response: ClientResponse) -> None:
    # Response checks
    assert response.status == HTTPStatus.NOT_FOUND
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert response_data['error']['code'] == 'not_found'
    assert response_data['error']['message'] == '404: Not Found'


async def check_response_for_authorized_user_permissions(response: ClientResponse) -> None:
    # Response checks
    assert response.status == HTTPStatus.FORBIDDEN
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert response_data['error']['code'] == 'forbidden'
    assert response_data['error']['message'] == '403: You do not have permission to perform this action.'


async def test_create_user(authorized_api_client, db_session):
    api_client, _ = authorized_api_client
    # Try to create user without all required fields
    partial_data = {
        'first_name': 'John',
        'last_name': 'Doe',
    }
    response = await api_client.post(url_for(views.UserCreateAPIView.URL_PATH), data=partial_data)
    # Response checks
    assert response.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert len(response_data['error']['fields'].keys()) == 2
    assert response_data['error']['fields'].keys() == {'email', 'password'}

    # Try to create user with invalid data
    invalid_data = {
        'first_name': 'John',
        'last_name': 'Doe',
        'email': 'invalid_email.com',
        'password': USER_TEST_PASSWORD[:5],
    }
    response = await api_client.post(url_for(views.UserCreateAPIView.URL_PATH), data=invalid_data)
    # Response checks
    assert response.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert len(response_data['error']['fields'].keys()) == 2
    assert response_data['error']['fields']['email'][0] == 'Not a valid email address.'
    assert response_data['error']['fields']['password'][0] == 'Shorter than minimum length 7.'

    # Creates a new user
    user_data = {
        'first_name': 'John',
        'last_name': 'Doe',
        'email': 'test_user@email.com',
        'password': USER_TEST_PASSWORD,
    }
    result = await db_session.execute(select(User).filter_by(email=user_data['email']))
    assert not result.scalar()
    response = await api_client.post(url_for(views.UserCreateAPIView.URL_PATH), data=user_data)
    # Response checks
    assert response.status == HTTPStatus.CREATED
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.UserDetailsResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['first_name'] == user_data['first_name']
    assert response_data['data']['last_name'] == user_data['last_name']
    assert response_data['data']['email'] == user_data['email']
    assert not response_data['data']['is_admin']  # False is default value
    # DB user checks
    result = await db_session.execute(select(User).filter_by(email=user_data['email']))
    user_from_db = result.scalar()
    assert user_from_db
    assert user_from_db.email == user_data['email']
    assert not user_from_db.is_admin

    # Try to create user with same data
    duplicate_user_data = user_data
    # Check user exists
    result = await db_session.execute(select(User).filter_by(email=duplicate_user_data['email']))
    assert result.first()
    response = await api_client.post(url_for(views.UserCreateAPIView.URL_PATH), data=duplicate_user_data)
    # Response checks
    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert len(response_data['error']['fields'].keys()) == 1
    assert response_data['error']['fields']['email'][0] == 'User with this email already exists.'


async def test_login_user(authorized_api_client, db_session):
    api_client, _ = authorized_api_client
    # Create user object without save user in database (checks invalid data)
    user = UserFactory()
    request_data = {'email': user.email, 'password': USER_TEST_PASSWORD}
    response = await api_client.post(url_for(views.LoginAPIView.URL_PATH), data=request_data)
    # Response checks
    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert response_data['error']['fields']['non_field_errors'][0] == 'Unable to log in with provided credentials.'

    # Then save user to database
    await user.async_save(db_session=db_session)

    # Check invalid password
    invalid_password_data = {'email': user.email, 'password': 'invalid_password'}
    response = await api_client.post(url_for(views.LoginAPIView.URL_PATH), data=invalid_password_data)
    # Response checks
    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert response_data['error']['fields']['non_field_errors'][0] == 'Unable to log in with provided credentials.'

    # Check valid data
    response = await api_client.post(url_for(views.LoginAPIView.URL_PATH), data=request_data)
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.JWTTokenResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['user']['first_name'] == user.first_name
    assert response_data['data']['user']['last_name'] == user.last_name
    assert not response_data['data']['user']['is_admin']
    assert response_data['data']['user']['email'] == user.email


async def test_get_user_list(authorized_api_client, db_session):
    api_client, user = authorized_api_client
    # Creates users pool
    result = await db_session.execute(select(func.count(User.id)))
    initial_users_quantity = result.scalar()
    additional_users = [
        UserFactory(is_admin=True) if i % 2 == 0 else UserFactory()  # to create some admin users
        for i in range(ADDITIONAL_OBJECTS_QUANTITY)
    ]
    await add_objects_to_db(objects_list=additional_users, db_session=db_session)

    # Get all users
    response = await api_client.get(url_for(views.UsersListAPIView.URL_PATH))
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.UserListResponseSchema().validate(response_data)
    assert not errors
    assert len(response_data['data']) == initial_users_quantity + ADDITIONAL_OBJECTS_QUANTITY
    assert any([i["is_admin"] for i in response_data["data"]])  # we have admins in list

    # Filter by email
    response = await api_client.get(url_for(views.UsersListAPIView.URL_PATH), params={'search': user.email})
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.UserListResponseSchema().validate(response_data)
    assert not errors
    assert len(response_data['data']) == 1
    assert response_data['data'][0]['id'] == user.id
    assert response_data['data'][0]['email'] == user.email
    assert response_data['data'][0]['first_name'] == user.first_name
    assert response_data['data'][0]['last_name'] == user.last_name
    assert response_data['data'][0]['is_admin'] == user.is_admin


async def test_retrieve_update_destroy_user(authorized_api_client, db_session):
    api_client, user = authorized_api_client
    other_user = UserFactory()
    await other_user.async_save(db_session=db_session)
    assert not user.is_admin  # specifies non-admin user

    # # Get methods
    # Get info about authorized user
    response = await api_client.get(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH, user_id=user.id))
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.UserDetailsResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['id'] == user.id
    assert response_data['data']['email'] == user.email
    assert response_data['data']['first_name'] == user.first_name
    assert response_data['data']['last_name'] == user.last_name
    assert response_data['data']['is_admin'] == user.is_admin

    # Get info about other_user
    response = await api_client.get(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH, user_id=other_user.id))
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.UserDetailsResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['id'] == other_user.id
    assert response_data['data']['email'] == other_user.email
    assert response_data['data']['first_name'] == other_user.first_name
    assert response_data['data']['last_name'] == other_user.last_name
    assert response_data['data']['is_admin'] == other_user.is_admin

    # Get info about not exists user
    result = await db_session.execute(select(User.id).order_by(desc(User.id)).limit(1))
    last_id = result.scalar()
    response = await api_client.get(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH, user_id=last_id + 100))
    await check_response_for_objects_exists(response)

    # # Patch methods
    # Attempt to update authorized user info with not unique email
    invalid_patch_data = {'email': other_user.email}
    response = await api_client.patch(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH, user_id=user.id),
                                      data=invalid_patch_data)
    # Response checks
    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert len(response_data['error']['fields'].keys()) == 1
    assert response_data['error']['fields']['email'][0] == 'User with this email already exists.'

    # Update authorized user info
    new_email = f'patched.{user.email}'
    valid_patch_data = {'email': new_email}
    response = await api_client.patch(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH, user_id=user.id),
                                      data=valid_patch_data)
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.UserDetailsResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['id'] == user.id
    assert response_data['data']['email'] == new_email
    assert response_data['data']['first_name'] == user.first_name
    assert response_data['data']['last_name'] == user.last_name
    assert response_data['data']['is_admin'] == user.is_admin
    # DB check
    await db_session.refresh(user)  # get updates from db
    assert user.email == new_email

    # Attempt to update not exists user
    result = await db_session.execute(select(User.id).order_by(desc(User.id)).limit(1))
    last_id = result.scalar()
    response = await api_client.patch(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH, user_id=last_id + 100),
                                      data=valid_patch_data)
    await check_response_for_objects_exists(response)

    # Attempt to update other_user with authorized non-admin user
    other_user_old_email = other_user.email
    other_user_new_email = f'patched.{other_user.email}'
    other_user_patch_data = {'email': other_user_new_email}
    response = await api_client.patch(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH, user_id=other_user.id),
                                      data=other_user_patch_data)
    await check_response_for_authorized_user_permissions(response)
    # DB check
    await db_session.refresh(other_user)  # get updates from db
    assert other_user.email == other_user_old_email

    # # Delete methods
    # Attempt to delete not exists user
    result = await db_session.execute(select(User.id).order_by(desc(User.id)).limit(1))
    last_id = result.scalar()
    response = await api_client.delete(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH, user_id=last_id + 100))
    await check_response_for_objects_exists(response)

    # Attempt to delete other_user by authorized non-admin user
    response = await api_client.delete(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH, user_id=other_user.id))
    await check_response_for_authorized_user_permissions(response)
    # DB check
    result = await db_session.execute(select(exists().where(User.id == other_user.id)))
    assert result.scalar()  # `exists` is True here

    # Delete authorized user
    response = await api_client.delete(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH, user_id=user.id))
    # Response checks
    assert response.status == HTTPStatus.NO_CONTENT
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert not response_data
    # DB check
    result = await db_session.execute(select(exists().where(User.id == user.id)))
    assert not result.scalar()

    # Admin-user actions
    admin_user = UserFactory(is_admin=True)
    await admin_user.async_save(db_session=db_session)
    api_client._session.headers["Authorization"] = f'Bearer {get_jwt_token_for_user(user=admin_user)}'
    assert admin_user.is_admin  # specifies admin user

    # Update other_user with authorized admin user
    response = await api_client.patch(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH,
                                              user_id=other_user.id),
                                      data=other_user_patch_data)
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.UserDetailsResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['id'] == other_user.id
    assert response_data['data']['email'] == other_user_new_email
    assert response_data['data']['first_name'] == other_user.first_name
    assert response_data['data']['last_name'] == other_user.last_name
    assert response_data['data']['is_admin'] == other_user.is_admin
    # DB check
    await db_session.refresh(other_user)  # get updates from db
    assert other_user.email == other_user_new_email

    # Delete other_user by authorized admin user
    response = await api_client.delete(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH,
                                               user_id=other_user.id))
    # Response checks
    assert response.status == HTTPStatus.NO_CONTENT
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert not response_data
    # DB check
    result = await db_session.execute(select(exists().where(User.id == other_user.id)))
    assert not result.scalar()


async def test_change_user_password(authorized_api_client, db_session):
    api_client, user = authorized_api_client
    assert User.check_user_password(raw_password=USER_TEST_PASSWORD, hashed_password=user.password)

    # Attempt to change user's password with invalid data
    new_password = 'New_Cool_Security_Password_<3_KeyUA***'
    confirm_new_password = new_password[:10]
    invalid_patch_data = {'new_password': new_password, 'confirm_new_password': confirm_new_password}
    response = await api_client.patch(url_for(views.UserChangePasswordAPIView.URL_PATH, user_id=user.id),
                                      data=invalid_patch_data)
    # Response checks
    assert response.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert len(response_data['error']['fields'].keys()) == 1
    assert response_data['error']['fields']['confirm_new_password'][0] == "The two password fields didn't match."

    # Change user's password
    confirm_new_password = new_password
    invalid_patch_data = {'new_password': new_password, 'confirm_new_password': confirm_new_password}
    response = await api_client.patch(url_for(views.UserChangePasswordAPIView.URL_PATH, user_id=user.id),
                                      data=invalid_patch_data)
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert not response_data
    # DB check
    await db_session.refresh(user)  # get updates from db
    assert not User.check_user_password(raw_password=USER_TEST_PASSWORD, hashed_password=user.password)
    assert User.check_user_password(raw_password=new_password, hashed_password=user.password)
