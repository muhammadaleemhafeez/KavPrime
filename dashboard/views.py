from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from Tickets.models import Ticket
from users.models import User
from inventory.models import AssetDetails


# -----------------------------
# Helper Function
# -----------------------------
def normalize_status(status):
    """
    Convert all PENDING_* statuses into IN_PROGRESS
    """
    status = status.upper()

    if status.startswith("PENDING"):
        return "IN_PROGRESS"

    if status in ["APPROVED", "COMPLETED", "REJECTED"]:
        return status

    return status  # fallback


# -----------------------------
# Unified Dashboard View
# -----------------------------
@require_http_methods(["GET"])
def dashboard_summary(request, employee_id=None, role_name=None):
    """
    Unified dashboard:
    - Employee dashboard: provide employee_id
    - Role dashboard: provide role_name (TEAM_PMO, SENIOR_PMO, ADMIN, FINANCE, HR)
    """

    # ------------------------------------------------
    # EMPLOYEE DASHBOARD
    # ------------------------------------------------
    if employee_id:
        try:
            user = User.objects.get(id=employee_id)
        except User.DoesNotExist:
            return JsonResponse({"error": "Employee not found"}, status=404)

        # Assets assigned to employee
        assets_qs = AssetDetails.objects.filter(user_id=employee_id)
        assets_by_status = dict(
            assets_qs.values("status").annotate(count=Count("id")).values_list("status", "count")
        )
        total_assets = assets_qs.count()
        total_quantity = assets_qs.aggregate(total=Coalesce(Sum("quantity_issued"), 0))["total"]

        # Tickets created by employee
        tickets_qs = Ticket.objects.filter(employee_id=employee_id)
        total_tickets = tickets_qs.count()

        # NORMALIZED TICKET STATUS COUNTS
        raw_ticket_status = tickets_qs.values("status").annotate(count=Count("id"))

        tickets_by_status = {}
        for row in raw_ticket_status:
            new_status = normalize_status(row["status"])
            tickets_by_status[new_status] = tickets_by_status.get(new_status, 0) + row["count"]

        return JsonResponse({
            "type": "employee_dashboard",
            "employee": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role_name
            },
            "tickets": {
                "total_created": total_tickets,
                "by_status": tickets_by_status
            },
            "assets": {
                "total_assets_rows": total_assets,
                "total_quantity_issued": total_quantity,
                "by_status": assets_by_status
            }
        }, status=200)

    # ------------------------------------------------
    # ROLE DASHBOARD (TEAM_PMO, SENIOR_PMO, ADMIN...)
    # ------------------------------------------------
    if role_name:
        users_in_role = User.objects.filter(role=role_name)
        user_ids = users_in_role.values_list('id', flat=True)

        # Tickets assigned to role OR created by users in this role
        tickets_qs = Ticket.objects.filter(current_role=role_name) | Ticket.objects.filter(employee_id__in=user_ids)
        tickets_qs = tickets_qs.distinct()
        total_tickets = tickets_qs.count()

        # NORMALIZED TICKET STATUS COUNTS
        raw_ticket_status = tickets_qs.values("status").annotate(count=Count("id"))

        tickets_by_status = {}
        for row in raw_ticket_status:
            new_status = normalize_status(row["status"])
            tickets_by_status[new_status] = tickets_by_status.get(new_status, 0) + row["count"]

        # Assets assigned to users in this role
        assets_qs = AssetDetails.objects.filter(user_id__in=user_ids)
        assets_by_status = dict(
            assets_qs.values("status").annotate(count=Count("id")).values_list("status", "count")
        )
        total_assets = assets_qs.count()
        total_quantity = assets_qs.aggregate(total=Coalesce(Sum("quantity_issued"), 0))["total"]

        response = {
            "type": "role_dashboard",
            "role": role_name,
            "total_tickets_created": total_tickets,
            "tickets_by_status": tickets_by_status,
            "total_assets_rows": total_assets,
            "total_quantity_issued": total_quantity,
            "assets_by_status": assets_by_status
        }

        # Admin: Add total registered users
        if role_name.upper() == "ADMIN":
            response["total_users_registered"] = User.objects.count()

        return JsonResponse(response, status=200)

    return JsonResponse({"error": "employee_id or role_name must be provided"}, status=400)
