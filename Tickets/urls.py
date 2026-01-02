from django.urls import path
from .views import create_ticket, list_tickets
from . import views
from . import views

urlpatterns = [
    path('create/', create_ticket),
    path('list/', list_tickets),
    path('update-ticket-status/', views.update_ticket_status, name='update_ticket_status'),
    # path('update-ticket-status/', views.update_ticket_status, name='update_ticket_status'),

    # ✅ add this
    path('ticket-history/<int:ticket_id>/', views.ticket_history, name='ticket_history'),
    path('escalate/<int:ticket_id>/', views.escalate_ticket, name='escalate_ticket'),


]
