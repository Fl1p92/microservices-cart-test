from http import HTTPStatus

from aiohttp import ClientResponse
from sqlalchemy import select, func, desc, exists

from cart.db.factories import ProductFactory, CartFactory, CartItemFactory
from cart.db.models import Product, Cart, CartItem
from cart.api import views, schema
from cart.utils import url_for, add_objects_to_db


ADDITIONAL_OBJECTS_QUANTITY = 5


async def check_response_for_objects_exists(response: ClientResponse) -> None:
    # Response checks
    assert response.status == HTTPStatus.NOT_FOUND
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert response_data['error']['code'] == 'not_found'
    assert response_data['error']['message'] == '404: Not Found'


async def test_get_products_list(authorized_api_client, db_session):
    api_client = authorized_api_client
    # Creates products pool
    result = await db_session.execute(select(func.count(Product.id)))
    initial_products_quantity = result.scalar()
    additional_products = [ProductFactory() for _ in range(ADDITIONAL_OBJECTS_QUANTITY - 1)]
    lost_product = ProductFactory(name='Find_me_if_u_can')  # additional product with non-random name
    additional_products.append(lost_product)
    await add_objects_to_db(objects_list=additional_products, db_session=db_session)

    # Get all products
    response = await api_client.get(url_for(views.ProductsListAPIView.URL_PATH))
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.ProductsListResponseSchema().validate(response_data)
    assert not errors
    assert len(response_data['data']) == initial_products_quantity + ADDITIONAL_OBJECTS_QUANTITY

    # Filter by name
    response = await api_client.get(url_for(views.ProductsListAPIView.URL_PATH), params={'search': 'Find_me'})
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.ProductsListResponseSchema().validate(response_data)
    assert not errors
    assert len(response_data['data']) == 1
    assert response_data['data'][0]['id'] == lost_product.id
    assert response_data['data'][0]['name'] == lost_product.name
    assert response_data['data'][0]['description'] == lost_product.description
    assert response_data['data'][0]['price'] == str(lost_product.price)


async def test_retrieve_destroy_cart(authorized_api_client, db_session):
    api_client = authorized_api_client
    result = await db_session.execute(select(func.count(Cart.user_id)))
    assert not result.scalar()  # carts table is empty
    new_user_id = 1

    # Get info about a non-existent cart
    response = await api_client.get(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=new_user_id))
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.CartResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['user_id'] == new_user_id
    assert response_data['data']['total_price'] == '0.00'
    assert not response_data['data']['cart_items']  # empty list
    result = await db_session.execute(select(func.count(Cart.user_id)))
    assert result.scalar() == 1

    # Get info about existent cart
    # Create new cart with cart item
    cart_item = CartItemFactory()
    await cart_item.async_save(db_session=db_session)
    cart = cart_item.cart
    result = await db_session.execute(select(func.count(Cart.user_id)))
    assert result.scalar() == 2
    response = await api_client.get(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=cart.user_id))
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.CartResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['user_id'] == cart.user_id
    assert response_data['data']['total_price'] == str(cart_item.product.price * cart_item.quantity)
    assert response_data['data']['cart_items']
    assert response_data['data']['cart_items'][0]['id'] == cart_item.id
    assert response_data['data']['cart_items'][0]['product_id'] == cart_item.product_id
    assert response_data['data']['cart_items'][0]['cart_id'] == cart_item.cart_id
    assert response_data['data']['cart_items'][0]['quantity'] == cart_item.quantity

    # Attempt to clear a non-existent cart
    result = await db_session.execute(select(Cart.user_id).order_by(desc(Cart.user_id)).limit(1))
    last_id = result.scalar()
    response = await api_client.delete(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=last_id + 100))
    await check_response_for_objects_exists(response)

    # Clear a existent cart
    response = await api_client.delete(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=cart.user_id))
    # Response checks
    assert response.status == HTTPStatus.NO_CONTENT
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert not response_data
    # DB check
    result = await db_session.execute(select(exists().where(Cart.user_id == cart.user_id)))
    assert result.scalar()  # cart not deleted
    result = await db_session.execute(select(exists().where(CartItem.cart_id == cart.user_id)))
    assert not result.scalar()  # but all cart items deleted

    # # Admin-user actions
    # admin_user = UserFactory(is_admin=True)
    # await admin_user.async_save(db_session=db_session)
    # api_client._session.headers["Authorization"] = f'Bearer {get_jwt_token_for_user(user=admin_user)}'
    # assert admin_user.is_admin  # specifies admin user
    #
    # # Update other_user with authorized admin user
    # response = await api_client.patch(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH,
    #                                           user_id=other_user.id),
    #                                   data=other_user_patch_data)
    # # Response checks
    # assert response.status == HTTPStatus.OK
    # assert response.content_type == 'application/json'
    # # Response data checks
    # response_data = await response.json()
    # errors = schema.UserDetailsResponseSchema().validate(response_data)
    # assert not errors
    # assert response_data['data']['id'] == other_user.id
    # assert response_data['data']['email'] == other_user_new_email
    # assert response_data['data']['first_name'] == other_user.first_name
    # assert response_data['data']['last_name'] == other_user.last_name
    # assert response_data['data']['is_admin'] == other_user.is_admin
    # # DB check
    # await db_session.refresh(other_user)  # get updates from db
    # assert other_user.email == other_user_new_email
    #
    # # Delete other_user by authorized admin user
    # response = await api_client.delete(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH,
    #                                            user_id=other_user.id))
    # # Response checks
    # assert response.status == HTTPStatus.NO_CONTENT
    # assert response.content_type == 'application/json'
    # # Response data checks
    # response_data = await response.json()
    # assert not response_data
    # # DB check
    # result = await db_session.execute(select(exists().where(User.id == other_user.id)))
    # assert not result.scalar()


async def test_create_cart_item(authorized_api_client, db_session):
    api_client = authorized_api_client
    cart = CartFactory()
    await cart.async_save(db_session=db_session)
    product = ProductFactory()
    await product.async_save(db_session=db_session)

    # Try to create cart_item without all required fields
    partial_data = {
        'quantity': 3,
    }
    response = await api_client.post(url_for(views.CartItemCreateAPIView.URL_PATH, cart_id=cart.user_id),
                                     data=partial_data)
    # Response checks
    assert response.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert len(response_data['error']['fields'].keys()) == 1
    assert response_data['error']['fields'].keys() == {'product_id'}

    # Try to create cart_item with invalid data
    invalid_data = {
        'product_id': product.id,
        'quantity': 6,
    }
    response = await api_client.post(url_for(views.CartItemCreateAPIView.URL_PATH, cart_id=cart.user_id),
                                     data=invalid_data)
    # Response checks
    assert response.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert len(response_data['error']['fields'].keys()) == 1
    assert response_data['error']['fields']['quantity'][0] == 'Must be greater than or equal to 1 and less than ' \
                                                              'or equal to 5.'

    # Creates a new cart_item
    result = await db_session.execute(select(func.count(CartItem.id)).where(CartItem.cart_id == cart.user_id))
    assert not result.scalar()  # cart is empty
    cart_item_data = {
        'product_id': product.id,
        'quantity': 3,
    }
    response = await api_client.post(url_for(views.CartItemCreateAPIView.URL_PATH, cart_id=cart.user_id),
                                     data=cart_item_data)
    # Response checks
    assert response.status == HTTPStatus.CREATED
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.CartResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['user_id'] == cart.user_id
    assert response_data['data']['total_price'] == str(product.price * cart_item_data['quantity'])
    assert response_data['data']['cart_items']
    assert response_data['data']['cart_items'][0]['product_id'] == cart_item_data['product_id']
    assert response_data['data']['cart_items'][0]['cart_id'] == cart.user_id
    assert response_data['data']['cart_items'][0]['quantity'] == cart_item_data['quantity']
    # DB check
    result = await db_session.execute(select(CartItem).filter_by(cart_id=cart.user_id))
    cart_item_from_db = result.scalar()
    assert cart_item_from_db
    assert cart_item_from_db.quantity == cart_item_data['quantity']
    assert cart_item_from_db.product_id == product.id

    # Try to create cart_item with same product
    duplicate_cart_item_data = cart_item_data
    # Check cart_item exists
    result = await db_session.execute(select(CartItem).filter_by(product_id=duplicate_cart_item_data['product_id'],
                                                                 cart_id=cart.user_id))
    assert result.first()
    response = await api_client.post(url_for(views.CartItemCreateAPIView.URL_PATH, cart_id=cart.user_id),
                                     data=duplicate_cart_item_data)
    # Response checks
    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert len(response_data['error']['fields'].keys()) == 1
    assert response_data['error']['fields']['product_id'][0] == "The product is already in cart. Please change " \
                                                                "the product or just update it's quantity."


async def test_update_destroy_cart_item(authorized_api_client, db_session):
    api_client = authorized_api_client
    cart_item = CartItemFactory()
    await cart_item.async_save(db_session=db_session)

    # Attempt to update cart_item with invalid quantity
    invalid_patch_data = {'quantity': 6}
    response = await api_client.patch(url_for(views.CartItemUpdateDestroyAPIView.URL_PATH, item_id=cart_item.id),
                                      data=invalid_patch_data)
    # Response checks
    assert response.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert len(response_data['error']['fields'].keys()) == 1
    assert response_data['error']['fields']['quantity'][0] == 'Must be greater than or equal to 1 and less than ' \
                                                              'or equal to 5.'

    # Update cart_item quantity
    new_quantity = (cart_item.quantity - 1) or (cart_item.quantity + 1)  # just in case if original quantity will be 1
    valid_patch_data = {'quantity': new_quantity}
    response = await api_client.patch(url_for(views.CartItemUpdateDestroyAPIView.URL_PATH, item_id=cart_item.id),
                                      data=valid_patch_data)
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.CartResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['user_id'] == cart_item.cart.user_id
    assert response_data['data']['total_price'] == str(cart_item.product.price * new_quantity)
    assert response_data['data']['cart_items']
    assert response_data['data']['cart_items'][0]['product_id'] == cart_item.product_id
    assert response_data['data']['cart_items'][0]['cart_id'] == cart_item.cart_id
    assert response_data['data']['cart_items'][0]['quantity'] == new_quantity
    # DB check
    await db_session.refresh(cart_item)  # get updates from db
    assert cart_item.quantity == new_quantity

    # Attempt to update not exists cart_item
    result = await db_session.execute(select(CartItem.id).order_by(desc(CartItem.id)).limit(1))
    last_id = result.scalar()
    response = await api_client.patch(url_for(views.CartItemUpdateDestroyAPIView.URL_PATH, item_id=last_id + 100),
                                      data=valid_patch_data)
    await check_response_for_objects_exists(response)

    # Attempt to update other_user with authorized non-admin user
    # other_user_old_email = other_user.email
    # other_user_new_email = f'patched.{other_user.email}'
    # other_user_patch_data = {'email': other_user_new_email}
    # response = await api_client.patch(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH, user_id=other_user.id),
    #                                   data=other_user_patch_data)
    # await check_response_for_authorized_user_permissions(response)
    # # DB check
    # await db_session.refresh(other_user)  # get updates from db
    # assert other_user.email == other_user_old_email

    # Attempt to delete not exists cart_item
    result = await db_session.execute(select(CartItem.id).order_by(desc(CartItem.id)).limit(1))
    last_id = result.scalar()
    response = await api_client.delete(url_for(views.CartItemUpdateDestroyAPIView.URL_PATH, item_id=last_id + 100))
    await check_response_for_objects_exists(response)

    # # Attempt to delete other_user by authorized non-admin user
    # response = await api_client.delete(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH,
    #                                    user_id=other_user.id))
    # await check_response_for_authorized_user_permissions(response)
    # # DB check
    # result = await db_session.execute(select(exists().where(User.id == other_user.id)))
    # assert result.scalar()  # `exists` is True here

    # Delete cart_item
    response = await api_client.delete(url_for(views.CartItemUpdateDestroyAPIView.URL_PATH, item_id=cart_item.id))
    # Response checks
    assert response.status == HTTPStatus.NO_CONTENT
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert not response_data
    # DB check
    result = await db_session.execute(select(exists().where(CartItem.id == cart_item.id)))
    assert not result.scalar()

    # Admin-user actions
    # admin_user = UserFactory(is_admin=True)
    # await admin_user.async_save(db_session=db_session)
    # api_client._session.headers["Authorization"] = f'Bearer {get_jwt_token_for_user(user=admin_user)}'
    # assert admin_user.is_admin  # specifies admin user
    #
    # # Update other_user with authorized admin user
    # response = await api_client.patch(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH,
    #                                           user_id=other_user.id),
    #                                   data=other_user_patch_data)
    # # Response checks
    # assert response.status == HTTPStatus.OK
    # assert response.content_type == 'application/json'
    # # Response data checks
    # response_data = await response.json()
    # errors = schema.UserDetailsResponseSchema().validate(response_data)
    # assert not errors
    # assert response_data['data']['id'] == other_user.id
    # assert response_data['data']['email'] == other_user_new_email
    # assert response_data['data']['first_name'] == other_user.first_name
    # assert response_data['data']['last_name'] == other_user.last_name
    # assert response_data['data']['is_admin'] == other_user.is_admin
    # # DB check
    # await db_session.refresh(other_user)  # get updates from db
    # assert other_user.email == other_user_new_email
    #
    # # Delete other_user by authorized admin user
    # response = await api_client.delete(url_for(views.UserRetrieveUpdateDestroyAPIView.URL_PATH,
    #                                            user_id=other_user.id))
    # # Response checks
    # assert response.status == HTTPStatus.NO_CONTENT
    # assert response.content_type == 'application/json'
    # # Response data checks
    # response_data = await response.json()
    # assert not response_data
    # # DB check
    # result = await db_session.execute(select(exists().where(User.id == other_user.id)))
    # assert not result.scalar()
