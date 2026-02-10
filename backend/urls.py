from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Workflow import
from Tickets.views_workflow import create_workflow_with_roles

urlpatterns = [
    path("admin/", admin.site.urls),

    # ✅ Users app APIs
    path("api/users/", include("users.urls")),  # Login, register, update, delete, workflows, roles

    # Tickets app APIs
    path("api/tickets/", include("Tickets.urls")),  

    # Inventory app APIs
    path("api/inventory/", include("inventory.urls")),  

    # Dashboard APIs
    path("api/dashboard/", include("dashboard.urls")),  

    # If you want a direct workflow create URL (optional, can also be under users)
    path("api/workflows/create-with-roles/", create_workflow_with_roles),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
