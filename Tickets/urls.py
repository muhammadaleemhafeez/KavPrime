from django.urls import path
from .views import create_ticket, list_tickets
from . import views

urlpatterns = [
    path('create/', create_ticket),
    path('list/', list_tickets),
    path('update-ticket-status/', views.update_ticket_status, name='update_ticket_status'),
]
