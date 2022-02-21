from cart.utils import fix_white_list_urls


async def test_fix_white_list_urls():

    test_urls = ['/api/v1/products/list/',
                 r'/api/v1/cart/{user_id:\d+}/',
                 r'/api/v1/cart-item/{cart_id:\d+}/create',
                 r'/api/v1/cart-item/{item_id:\d+}/']

    fixed_urls = fix_white_list_urls(test_urls)
    assert fixed_urls[0] == test_urls[0]  # the same
    assert fixed_urls[1] == '/api/v1/cart/.*/'
    assert fixed_urls[2] == '/api/v1/cart-item/.*/create'
    assert fixed_urls[3] == '/api/v1/cart-item/.*/'
