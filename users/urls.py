from django.urls import path
from .views import register_user, login_user, update_user, delete_user, get_all_users
from . import views_roles

urlpatterns = [
    path("register/", register_user, name="register"),
    path("login/", login_user, name="login"),
    path("update/", update_user),
    path("delete/", delete_user),
    path("getUsers/", get_all_users),

    # ✅ Role Management APIs (for Postman + Admin-like control)
    path("roles/", views_roles.list_roles, name="list_roles"),
    path("roles/add/", views_roles.add_role, name="add_role"),
    path("roles/<int:role_id>/active/", views_roles.set_role_active, name="set_role_active"),
]
