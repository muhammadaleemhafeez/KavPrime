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
    return_all_employee_assets,
    create_purchase_request,
    list_purchase_requests
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


    # return all asset when employee leaving company 

    path('employee-return-assets/<int:employee_id>/', return_all_employee_assets),

    # request for inventory to finance

    path("create-purchase-request/", views.create_purchase_request),

    # finace approval URL
    path("purchase-request/<int:request_id>/finance-approve/", views.finance_approve_request),

    # HR approval URL
    path("purchase-request/<int:request_id>/hr-approve/", views.hr_approve_request),


    #create purchase request 
    # path("create-purchase-request/", create_purchase_request, name="create_purchase_request"),

    # finance purchase add record 
    path("purchase-request/<int:request_id>/finance-purchase/", views.finance_mark_as_purchased, name="finance_purchase_request"),

    # list of purchse 

    path("purchase-requests/", list_purchase_requests, name="list_purchase_requests"),


    # vendor url
    path("add-vendor/", views.add_vendor, name="add_vendor"),

    # vendor list url
    path("vendors/", views.list_vendors, name="list_vendors"),


]
