from django.urls import path
from .views import register_user, login_user,update_user,delete_user

urlpatterns = [
    path("register/", register_user, name="register"),
    path("login/", login_user, name="login"),
    path('update/', update_user),
    path('delete/', delete_user),
]
