from django.urls import path
from .views import register_user, login_user, update_user, delete_user, get_all_users, upload_employee_image
from . import views_roles
from . import views

# from .views_roles import create_workflow_with_roles
from .views import list_team_pmo
from Tickets.views_workflow import create_workflow_with_roles

urlpatterns = [
    path("register/", register_user, name="register"),
    path("login/", login_user, name="login"),
    path("update/", update_user),
    path("delete/", delete_user),
    path("getUsers/", get_all_users),
    path("mark-exited/", views.mark_employee_exited),
    path("upload-image/", views.upload_employee_image),

    #list of team_pmo
    path("team-pmo/list/", list_team_pmo, name="list_team_pmo"),
    

    # New API for image upload
    path("upload_image/", upload_employee_image, name="upload_image"),  

    # ✅ Role Management APIs (for Postman + Admin-like control)
    path("roles/", views_roles.list_roles, name="list_roles"),
    path("roles/add/", views_roles.add_role, name="add_role"),
    path("roles/<int:role_id>/active/", views_roles.set_role_active, name="set_role_active"),

    path("api/workflows/create-with-roles/", create_workflow_with_roles),
    path("api/workflows/", views_roles.list_all_workflows, name="list_all_workflows"),
]
