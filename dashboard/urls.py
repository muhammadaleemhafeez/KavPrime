from django.urls import path
from .views import dashboard_summary

urlpatterns = [
    # Employee dashboard
    path("employee/<int:employee_id>/summary/", dashboard_summary, name="employee_dashboard"),

    # Role dashboard
    path("role/<str:role_name>/summary/", dashboard_summary, name="role_dashboard"),
]
