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


async def check_response_for_authorized_user_permissions(response: ClientResponse) -> None:
    # Response checks
    assert response.status == HTTPStatus.FORBIDDEN
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert response_data['error']['code'] == 'forbidden'
    assert response_data['error']['message'] == '403: You do not have permission to perform this action.'


#####################################################################
# Integration tests. Make sure the `customers` service is available #
#####################################################################
async def test_grpc_server_errors(authorized_api_client):
    api_client, non_admin_jwt, _, user_id = authorized_api_client
    # Send request without Authorization header
    response = await api_client.get(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=user_id))
    # Response checks
    assert response.status == HTTPStatus.FORBIDDEN
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert response_data['error']['code'] == 'forbidden'
    assert response_data['error']['message'] == '403: Invalid authorization header'

    # Send request with invalid JWT token
    api_client._session.headers["Authorization"] = 'qwasddqwd'
    response = await api_client.get(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=user_id))
    # Response checks
    assert response.status == HTTPStatus.FORBIDDEN
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert response_data['error']['code'] == 'forbidden'
    assert response_data['error']['message'] == '403: Invalid JWT token'

    # Send request with invalid JWT token scheme
    api_client._session.headers["Authorization"] = 'Beareraaa qwasddqwd'
    response = await api_client.get(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=user_id))
    # Response checks
    assert response.status == HTTPStatus.FORBIDDEN
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert response_data['error']['code'] == 'forbidden'
    assert response_data['error']['message'] == '403: Invalid token scheme'


async def test_get_products_list(authorized_api_client, db_session):
    api_client, _, _, _ = authorized_api_client
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
    api_client, non_admin_jwt, admin_jwt, user_id = authorized_api_client
    other_user_id = user_id + 100500
    result = await db_session.execute(select(func.count(Cart.user_id)))
    assert not result.scalar()  # carts table is empty
    api_client._session.headers["Authorization"] = non_admin_jwt

    # Get info about a non-existent user's cart
    response = await api_client.get(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=user_id))
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.CartResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['user_id'] == user_id
    assert response_data['data']['total_price'] == '0.00'
    assert not response_data['data']['cart_items']  # empty list
    result = await db_session.execute(select(func.count(Cart.user_id)))
    assert result.scalar() == 1
    user_cart_result = await db_session.execute(select(Cart).filter_by(user_id=user_id))
    user_cart = user_cart_result.scalar()
    assert user_cart

    # Get info about existent user's cart
    # Create new cart with cart item
    cart_item = CartItemFactory(cart=user_cart)
    await cart_item.async_save(db_session=db_session)
    result = await db_session.execute(select(func.count(Cart.user_id)))
    assert result.scalar() == 1
    response = await api_client.get(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=user_cart.user_id))
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.CartResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['user_id'] == user_cart.user_id
    assert response_data['data']['total_price'] == str(cart_item.product.price * cart_item.quantity)
    assert response_data['data']['cart_items']
    assert response_data['data']['cart_items'][0]['id'] == cart_item.id
    assert response_data['data']['cart_items'][0]['product_id'] == cart_item.product_id
    assert response_data['data']['cart_items'][0]['cart_id'] == cart_item.cart_id
    assert response_data['data']['cart_items'][0]['quantity'] == cart_item.quantity

    # Attempt to get info about other user's cart
    response = await api_client.get(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=other_user_id))
    await check_response_for_authorized_user_permissions(response)

    # Clear an existent user's cart
    response = await api_client.delete(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=user_cart.user_id))
    # Response checks
    assert response.status == HTTPStatus.NO_CONTENT
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert not response_data
    # DB check
    result = await db_session.execute(select(exists().where(Cart.user_id == user_cart.user_id)))
    assert result.scalar()  # cart not deleted
    result = await db_session.execute(select(exists().where(CartItem.cart_id == user_cart.user_id)))
    assert not result.scalar()  # but all cart items deleted

    # Attempt to clear other user's cart
    response = await api_client.delete(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=other_user_id))
    await check_response_for_authorized_user_permissions(response)

    # Admin-user actions
    api_client._session.headers["Authorization"] = admin_jwt
    result = await db_session.execute(select(func.count(Cart.user_id)))
    assert result.scalar() == 1
    # Get info about a non-existent other user's cart
    response = await api_client.get(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=other_user_id))
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.CartResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['user_id'] == other_user_id
    assert response_data['data']['total_price'] == '0.00'
    assert not response_data['data']['cart_items']  # empty list
    result = await db_session.execute(select(func.count(Cart.user_id)))
    assert result.scalar() == 2
    other_user_cart_result = await db_session.execute(select(Cart).filter_by(user_id=other_user_id))
    other_user_cart = other_user_cart_result.scalar()
    assert other_user_cart

    # Get info about existent other user's cart
    # Create new cart with cart item
    other_cart_item = CartItemFactory(cart=other_user_cart)
    await other_cart_item.async_save(db_session=db_session)
    result = await db_session.execute(select(func.count(Cart.user_id)))
    assert result.scalar() == 2
    response = await api_client.get(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=other_user_cart.user_id))
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.CartResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['user_id'] == other_user_cart.user_id
    assert response_data['data']['total_price'] == str(other_cart_item.product.price * other_cart_item.quantity)
    assert response_data['data']['cart_items']
    assert response_data['data']['cart_items'][0]['id'] == other_cart_item.id
    assert response_data['data']['cart_items'][0]['product_id'] == other_cart_item.product_id
    assert response_data['data']['cart_items'][0]['cart_id'] == other_cart_item.cart_id
    assert response_data['data']['cart_items'][0]['quantity'] == other_cart_item.quantity

    # Clear an existent other user's cart
    response = await api_client.delete(url_for(views.CartRetrieveDestroyAPIView.URL_PATH,
                                               user_id=other_user_cart.user_id))
    # Response checks
    assert response.status == HTTPStatus.NO_CONTENT
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert not response_data
    # DB check
    result = await db_session.execute(select(exists().where(Cart.user_id == other_user_cart.user_id)))
    assert result.scalar()  # cart not deleted
    result = await db_session.execute(select(exists().where(CartItem.cart_id == other_user_cart.user_id)))
    assert not result.scalar()  # but all cart items deleted

    # Clear a non-existent other user's cart
    result = await db_session.execute(select(Cart.user_id).order_by(desc(Cart.user_id)).limit(1))
    last_id = result.scalar()
    response = await api_client.delete(url_for(views.CartRetrieveDestroyAPIView.URL_PATH, user_id=last_id + 100))
    await check_response_for_objects_exists(response)


async def test_create_cart_item(authorized_api_client, db_session):
    api_client, non_admin_jwt, admin_jwt, user_id = authorized_api_client
    api_client._session.headers["Authorization"] = non_admin_jwt
    cart = CartFactory(user_id=user_id)
    await cart.async_save(db_session=db_session)
    other_cart = CartFactory()
    await other_cart.async_save(db_session=db_session)
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

    # Create a new cart_item
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

    # Try to create cart item in the other cart
    other_cart_item_data = {
        'product_id': product.id,
        'quantity': 3,
    }
    response = await api_client.post(url_for(views.CartItemCreateAPIView.URL_PATH, cart_id=other_cart.user_id),
                                     data=other_cart_item_data)
    await check_response_for_authorized_user_permissions(response)

    # Admin-user actions
    api_client._session.headers["Authorization"] = admin_jwt
    # Create a new cart_item in the other cart
    response = await api_client.post(url_for(views.CartItemCreateAPIView.URL_PATH, cart_id=other_cart.user_id),
                                     data=other_cart_item_data)
    # Response checks
    assert response.status == HTTPStatus.CREATED
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.CartResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['user_id'] == other_cart.user_id
    assert response_data['data']['total_price'] == str(product.price * other_cart_item_data['quantity'])
    assert response_data['data']['cart_items']
    assert response_data['data']['cart_items'][0]['product_id'] == other_cart_item_data['product_id']
    assert response_data['data']['cart_items'][0]['cart_id'] == other_cart.user_id
    assert response_data['data']['cart_items'][0]['quantity'] == other_cart_item_data['quantity']
    # DB check
    result = await db_session.execute(select(CartItem).filter_by(cart_id=other_cart.user_id))
    cart_item_from_db = result.scalar()
    assert cart_item_from_db
    assert cart_item_from_db.quantity == other_cart_item_data['quantity']
    assert cart_item_from_db.product_id == product.id

    # Try to create cart item in the non-existing cart
    result = await db_session.execute(select(Cart.user_id).order_by(desc(Cart.user_id)).limit(1))
    last_id = result.scalar()
    response = await api_client.post(url_for(views.CartItemCreateAPIView.URL_PATH, cart_id=last_id + 100),
                                     data=other_cart_item_data)
    await check_response_for_objects_exists(response)


async def test_update_destroy_cart_item(authorized_api_client, db_session):
    api_client, non_admin_jwt, admin_jwt, user_id = authorized_api_client
    api_client._session.headers["Authorization"] = non_admin_jwt
    cart_item = CartItemFactory(cart=CartFactory(user_id=user_id))
    await cart_item.async_save(db_session=db_session)
    other_cart_item = CartItemFactory()
    await other_cart_item.async_save(db_session=db_session)

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

    # Attempt to update other cart_item
    response = await api_client.patch(url_for(views.CartItemUpdateDestroyAPIView.URL_PATH, item_id=other_cart_item.id),
                                      data=valid_patch_data)
    await check_response_for_authorized_user_permissions(response)

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

    # Attempt to delete other cart_item
    response = await api_client.delete(url_for(views.CartItemUpdateDestroyAPIView.URL_PATH, item_id=other_cart_item.id))
    await check_response_for_authorized_user_permissions(response)

    # Admin-user actions
    api_client._session.headers["Authorization"] = admin_jwt
    # Update other cart_item quantity
    # Just in case if original quantity will be 1
    new_quantity = (other_cart_item.quantity - 1) or (other_cart_item.quantity + 1)
    valid_patch_data = {'quantity': new_quantity}
    response = await api_client.patch(url_for(views.CartItemUpdateDestroyAPIView.URL_PATH, item_id=other_cart_item.id),
                                      data=valid_patch_data)
    # Response checks
    assert response.status == HTTPStatus.OK
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    errors = schema.CartResponseSchema().validate(response_data)
    assert not errors
    assert response_data['data']['user_id'] == other_cart_item.cart.user_id
    assert response_data['data']['total_price'] == str(other_cart_item.product.price * new_quantity)
    assert response_data['data']['cart_items']
    assert response_data['data']['cart_items'][0]['product_id'] == other_cart_item.product_id
    assert response_data['data']['cart_items'][0]['cart_id'] == other_cart_item.cart_id
    assert response_data['data']['cart_items'][0]['quantity'] == new_quantity
    # DB check
    await db_session.refresh(other_cart_item)  # get updates from db
    assert other_cart_item.quantity == new_quantity

    # Attempt to update not exists cart_item
    result = await db_session.execute(select(CartItem.id).order_by(desc(CartItem.id)).limit(1))
    last_id = result.scalar()
    response = await api_client.patch(url_for(views.CartItemUpdateDestroyAPIView.URL_PATH, item_id=last_id + 100),
                                      data=valid_patch_data)
    await check_response_for_objects_exists(response)

    # Delete other cart_item
    response = await api_client.delete(url_for(views.CartItemUpdateDestroyAPIView.URL_PATH, item_id=other_cart_item.id))
    # Response checks
    assert response.status == HTTPStatus.NO_CONTENT
    assert response.content_type == 'application/json'
    # Response data checks
    response_data = await response.json()
    assert not response_data
    # DB check
    result = await db_session.execute(select(exists().where(CartItem.id == other_cart_item.id)))
    assert not result.scalar()

    # Attempt to delete not exists cart_item
    result = await db_session.execute(select(CartItem.id).order_by(desc(CartItem.id)).limit(1))
    last_id = result.scalar()
    response = await api_client.delete(url_for(views.CartItemUpdateDestroyAPIView.URL_PATH, item_id=last_id + 100))
    await check_response_for_objects_exists(response)
