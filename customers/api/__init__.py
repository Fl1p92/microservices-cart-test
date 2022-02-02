from .views import LoginAPIView, UserCreateAPIView, UsersListAPIView, UserRetrieveUpdateDestroyAPIView, \
    UserChangePasswordAPIView


API_VIEWS = (
    LoginAPIView,  # auth
    UserCreateAPIView, UsersListAPIView, UserRetrieveUpdateDestroyAPIView, UserChangePasswordAPIView  # users
)
JWT_WHITE_LIST = (LoginAPIView.URL_PATH, UserCreateAPIView.URL_PATH)
