from django.urls import path
from .views import (
    add_inventory,
    update_inventory,
    delete_inventory,
    list_inventory,
    issue_inventory
)

urlpatterns = [
    path('add/', add_inventory),
    path('update/', update_inventory),
    path('delete/', delete_inventory),
    path('list/', list_inventory),
    path('issue/', issue_inventory),

]
