from django.urls import path
from .views import employee_dashboard_summary

urlpatterns = [
    path("employee/<int:employee_id>/summary/", employee_dashboard_summary),
]
