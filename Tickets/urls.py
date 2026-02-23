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
    # path("update-ticket-status/", views.update_ticket_status, name="update_ticket_status"),

    # History by employee_id 
    path("ticket-history/<int:employee_id>/", views.ticket_history, name="ticket-history"),

    # DELETE ticket API
    path("delete/<int:ticket_id>/", delete_ticket, name="delete_ticket"),


    # Ticket history by ticket_id
    path('ticket-history/ticket/<int:ticket_id>/', views.ticket_history, name='ticket-history-ticket'),

    

    # list of workflow
    path("workflows/", views_workflow.list_workflows, name="list_workflows"),
    
    # ticket Assigned dashbaord
    path('dashboard/<int:user_id>/', views.dashboard_tickets, name='dashboard_tickets'),


    #Action on ticket Approve | Reject
    path('action/<int:ticket_id>/', views.ticket_action, name='ticket_action'),
]
