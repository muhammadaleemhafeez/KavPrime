from django.urls import path
from .views import create_ticket, list_tickets
from . import views
from . import views_workflow

urlpatterns = [
    # Ticket APIs
    path("create/", create_ticket),
    path("list/", list_tickets),
    path("update-ticket-status/", views.update_ticket_status, name="update_ticket_status"),

    # History
    path("ticket-history/<int:employee_id>/", views.ticket_history, name="ticket-history"),

    # Manual escalation
    path("escalate/<int:ticket_id>/", views.escalate_ticket, name="escalate_ticket"),

    # Email process actions
    path("team-pmo-action/<int:ticket_id>/", views.team_pmo_action),
    path("admin-complete/<int:ticket_id>/", views.admin_complete),

    # ✅ Workflow Management APIs (for Postman + Admin-like control)
    path("workflows/", views_workflow.list_workflows, name="list_workflows"),
    path("workflows/create/", views_workflow.create_workflow, name="create_workflow"),
    path("workflows/<int:workflow_id>/steps/add/", views_workflow.add_workflow_step, name="add_workflow_step"),
    path("workflows/<int:workflow_id>/activate/", views_workflow.activate_workflow, name="activate_workflow"),

     # ✅ Workflow fecching first role base on is_active is true
    path("workflows/active/step1-role/", views_workflow.active_workflow_step1_role, name="active_step1_role"),

]
