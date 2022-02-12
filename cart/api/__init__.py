from .views import ProductsListAPIView, CartRetrieveDestroyAPIView, CartItemCreateAPIView, CartItemUpdateDestroyAPIView


API_VIEWS = (
    ProductsListAPIView,  # products
    CartRetrieveDestroyAPIView,  # cart
    CartItemCreateAPIView, CartItemUpdateDestroyAPIView  # cart items
)
