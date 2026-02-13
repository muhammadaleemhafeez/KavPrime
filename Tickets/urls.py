from django.urls import path
from .views import create_ticket, list_tickets, delete_ticket
from . import views
from . import views_workflow

from .views import ticket_action

urlpatterns = [
    # Ticket APIs
    path("create/", create_ticket),
    path("list/", list_tickets),

    # get all list of tickets
    path("list/all/", views.list_all_tickets),

    #update ticket staus
    path("update-ticket-status/", views.update_ticket_status, name="update_ticket_status"),

    # History by employee_id 
    path("ticket-history/<int:employee_id>/", views.ticket_history, name="ticket-history"),

    # DELETE ticket API
    path("delete/<int:ticket_id>/", delete_ticket, name="delete_ticket"),


    # Ticket history by ticket_id
    path('ticket-history/ticket/<int:ticket_id>/', views.ticket_history, name='ticket-history-ticket'),

    

    # ticket approval or rejection dynamically
    # path('action/<int:ticket_id>/', ticket_action, name="ticket_action"),

    # Manual escalation
    # path("escalate/<int:ticket_id>/", views.escalate_ticket, name="escalate_ticket"),

    # Email process actions
    # path("team-pmo-action/<int:ticket_id>/", views.team_pmo_action),
    # path("admin-complete/<int:ticket_id>/", views.admin_complete),

    # ✅ Workflow Management APIs (for Postman + Admin-like control)
    path("workflows/", views_workflow.list_workflows, name="list_workflows"),
    path("workflows/create/", views_workflow.create_workflow, name="create_workflow"),
    path("workflows/<int:workflow_id>/steps/add/", views_workflow.add_workflow_step, name="add_workflow_step"),
    path("workflows/<int:workflow_id>/activate/", views_workflow.activate_workflow, name="activate_workflow"),

     # ✅ Workflow fecching first role base on is_active is true
    path("workflows/active/step1-role/", views_workflow.active_workflow_step1_role, name="active_step1_role"),


    path('dashboard/<int:user_id>/', views.dashboard_tickets, name='dashboard_tickets'),

    path('action/<int:ticket_id>/', views.ticket_action, name='ticket_action'),
]
