from django.urls import path
from . import views
from .views import (
    add_inventory,
    update_inventory,
    delete_inventory,
    list_inventory,
    issue_inventory,
    list_assets,
    get_employee_assets,
    get_inventory_assets,
    get_asset_detail,
)

urlpatterns = [
    path('add/', add_inventory, name='add_inventory'),
    path('update/', update_inventory, name='update_inventory'),
    path('delete/', delete_inventory, name='delete_inventory'),
    path('list/', list_inventory, name='list_inventory'),
    path('issue/', issue_inventory, name='issue_inventory'),
    path('assets/', list_assets, name='list_assets'),
    path('assets/employee/<int:employee_id>/', get_employee_assets, name='employee_assets'),
    # path('assets/inventory/<int:inventory_id>/', get_inventory_assets, name='inventory_assets'),
    path("inventory-assets/<int:inventory_id>/", views.get_inventory_assets),
    path('assets/<int:asset_id>/', get_asset_detail, name='asset_detail'),

    path("return-asset/", views.return_asset),
]
