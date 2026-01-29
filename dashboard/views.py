from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from users.models import User
from inventory.models import AssetDetails
from Tickets.models import Ticket


@require_http_methods(["GET"])
def employee_dashboard_summary(request, employee_id):
    # 1) Validate employee
    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    # 2) Assets summary (AssetDetails rows + total quantity)
    # assets_qs = AssetDetails.objects.filter(user_id=employee_id)
    assets_qs = AssetDetails.objects.filter(user_id=employee_id, status="ISSUED")


    # count rows per status
    assets_by_status = dict(
        assets_qs.values("status").annotate(count=Count("id")).values_list("status", "count")
    )

    total_assets_rows = assets_qs.count()
    total_quantity_issued = assets_qs.aggregate(
        total=Coalesce(Sum("quantity_issued"), 0)
    )["total"]

    # 3) Tickets summary (Ticket created by employee)
    tickets_qs = Ticket.objects.filter(employee_id=employee_id)

    tickets_by_status = dict(
        tickets_qs.values("status").annotate(count=Count("id")).values_list("status", "count")
    )

    return JsonResponse({
        "employee": {
            "id": employee.id,
            "name": employee.name,
            "email": employee.email,
            "role": employee.role_name
        },
        "assets": {
            "total_assigned_assets_rows": total_assets_rows,
            "total_quantity_issued": total_quantity_issued,
            "by_status": {
                "ISSUED": assets_by_status.get("ISSUED", 0),
                "RETURNED": assets_by_status.get("RETURNED", 0),
                "DAMAGED": assets_by_status.get("DAMAGED", 0),
            }
        },
        "tickets": {
            "total_created": tickets_qs.count(),
            "by_status": {
                # show your key statuses + keep others if you want
                "APPROVED": tickets_by_status.get("APPROVED", 0),
                "REJECTED": tickets_by_status.get("REJECTED", 0),
                "COMPLETED": tickets_by_status.get("COMPLETED", 0),
                "PENDING_TEAM_PMO": tickets_by_status.get("PENDING_TEAM_PMO", 0),
                "PENDING_SENIOR_PMO": tickets_by_status.get("PENDING_SENIOR_PMO", 0),
                "PENDING_ADMIN": tickets_by_status.get("PENDING_ADMIN", 0),
            }
        }
    }, status=200)
