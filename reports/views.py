# reports/views.py
import csv
from io import StringIO

from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth, TruncDate

from inventory.models import Asset, AssetDetails, PurchaseRequest, Vendor
from Tickets.models import Ticket, AssignedTicket, Workflow, WorkflowStep
from users.models import User

# ✅ JWT auth
from users.jwt_decorators import jwt_required


# ============================================================
# HELPER UTILITIES
# ============================================================

def _date_filters(request):
    from_date = request.GET.get("from_date")
    to_date   = request.GET.get("to_date")
    return from_date, to_date


def _apply_date_range(qs, field, from_date, to_date):
    if from_date:
        try:
            qs = qs.filter(**{f"{field}__date__gte": from_date})
        except Exception:
            qs = qs.filter(**{f"{field}__gte": from_date})
    if to_date:
        try:
            qs = qs.filter(**{f"{field}__date__lte": to_date})
        except Exception:
            qs = qs.filter(**{f"{field}__lte": to_date})
    return qs


def _wants_csv(request):
    return (
        request.GET.get("format", "").lower() == "csv"
        or "text/csv" in request.META.get("HTTP_ACCEPT", "")
    )


def _csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    )
    writer = csv.DictWriter(response, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return response


def _paginate(request, data):
    """
    Pagination helper.
    Query params: ?page=1&limit=10
    - page  starts at 1 (default: 1)
    - limit default: 10
    CSV requests skip pagination and return all rows.
    """
    try:
        page  = max(1, int(request.GET.get("page",  1)))
        limit = max(1, int(request.GET.get("limit", 10)))
    except (ValueError, TypeError):
        page  = 1
        limit = 10

    total       = len(data)
    start       = (page - 1) * limit
    end         = start + limit
    total_pages = max(1, (total + limit - 1) // limit)

    return {
        "page":        page,
        "limit":       limit,
        "total":       total,
        "total_pages": total_pages,
        "has_next":    page < total_pages,
        "has_prev":    page > 1,
        "data":        data[start:end],
    }


# ============================================================
# 1. ASSET & INVENTORY REPORTS
# ============================================================

@require_http_methods(["GET"])
@jwt_required
def report_asset_summary(request):
    assets = Asset.objects.all()

    by_status    = list(assets.values("status").annotate(count=Count("id")))
    by_category  = list(assets.values("category").annotate(count=Count("id")))
    by_condition = list(assets.values("condition").annotate(count=Count("id")))
    by_warranty  = list(assets.values("warranty_status").annotate(count=Count("id")))
    total_value  = assets.aggregate(total=Sum("purchase_price"))["total"] or 0

    if _wants_csv(request):
        rows = []
        for r in by_status:
            rows.append({"group": "by_status",          "key": r["status"],          "count": r["count"]})
        for r in by_category:
            rows.append({"group": "by_category",        "key": r["category"],        "count": r["count"]})
        for r in by_condition:
            rows.append({"group": "by_condition",       "key": r["condition"],       "count": r["count"]})
        for r in by_warranty:
            rows.append({"group": "by_warranty_status", "key": r["warranty_status"], "count": r["count"]})
        rows.append({"group": "TOTAL_ASSETS",         "key": "total",       "count": assets.count()})
        rows.append({"group": "TOTAL_PURCHASE_VALUE", "key": "total_value", "count": float(total_value)})
        return _csv_response("asset_summary", ["group", "key", "count"], rows)

    return JsonResponse({
        "report":               "Asset Summary",
        "generated_at":         timezone.now().isoformat(),
        "total_assets":         assets.count(),
        "total_purchase_value": float(total_value),
        "by_status":            by_status,
        "by_category":          by_category,
        "by_condition":         by_condition,
        "by_warranty_status":   by_warranty,
    })


@require_http_methods(["GET"])
@jwt_required
def report_asset_full_list(request):
    from_date, to_date = _date_filters(request)
    category  = request.GET.get("category")
    status    = request.GET.get("status")
    condition = request.GET.get("condition")

    # ✅ FIX: added "vendor" to select_related
    assets = Asset.objects.select_related("assigned_to", "vendor").all()
    if category:
        assets = assets.filter(category__iexact=category)
    if status:
        assets = assets.filter(status__iexact=status)
    if condition:
        assets = assets.filter(condition__iexact=condition)
    assets = _apply_date_range(assets, "purchase_date", from_date, to_date)

    rows = []
    for a in assets:
        rows.append({
            "asset_id":           a.id,
            "asset_tag":          a.asset_tag,
            "brand":              a.brand,
            "model_name":         a.model_name,
            "category":           a.category,
            "status":             a.status,
            "condition":          a.condition,
            "total_quantity":     a.total_quantity,
            "available_quantity": a.available_quantity,
            "issued_quantity":    a.issued_quantity,
            "purchase_date":      a.purchase_date.isoformat() if a.purchase_date else "",
            "purchase_price":     float(a.purchase_price) if a.purchase_price else "",
            "vendor_name":        a.vendor.name if a.vendor else "",   # ✅ FIX
            "warranty_status":    a.warranty_status,
            "warranty_end":       a.warranty_end.isoformat() if a.warranty_end else "",
            "assigned_to":        a.assigned_to.name if a.assigned_to else "",
            "current_location":   a.current_location or "",
        })

    if _wants_csv(request):
        headers = [
            "asset_id","asset_tag","brand","model_name","category","status","condition",
            "total_quantity","available_quantity","issued_quantity","purchase_date",
            "purchase_price","vendor_name","warranty_status","warranty_end",
            "assigned_to","current_location",
        ]
        return _csv_response("asset_full_list", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":       "Full Asset List",
        "generated_at": timezone.now().isoformat(),
        "filters":      {"category": category, "status": status, "condition": condition},
        "total":        paginated["total"],
        "total_pages":  paginated["total_pages"],
        "page":         paginated["page"],
        "limit":        paginated["limit"],
        "has_next":     paginated["has_next"],
        "has_prev":     paginated["has_prev"],
        "assets":       paginated["data"],
    })


@require_http_methods(["GET"])
@jwt_required
def report_asset_issue_return_history(request):
    from_date, to_date = _date_filters(request)
    asset_id    = request.GET.get("asset_id")
    employee_id = request.GET.get("employee_id")
    status      = request.GET.get("status")

    records = AssetDetails.objects.select_related("asset", "user", "issued_by").all()
    if asset_id:
        records = records.filter(asset_id=asset_id)
    if employee_id:
        records = records.filter(user_id=employee_id)
    if status:
        records = records.filter(status__iexact=status)
    records = _apply_date_range(records, "created_at", from_date, to_date)

    rows = []
    for r in records:
        rows.append({
            "record_id":       r.id,
            "asset_id":        r.asset.id if r.asset else "",
            "asset_tag":       r.asset.asset_tag if r.asset else "",
            "asset_category":  r.asset.category if r.asset else "",
            "brand":           r.asset.brand if r.asset else "",
            "model_name":      r.asset.model_name if r.asset else "",
            "employee_id":     r.user.id,
            "employee_name":   r.user.name,
            "employee_email":  r.user.email,
            "quantity_issued": r.quantity_issued,
            "status":          r.status,
            "issued_by":       r.issued_by.name if r.issued_by else "",
            "issued_date":     r.created_at.isoformat(),
            "return_date":     r.return_date.isoformat() if r.return_date else "",
            "remarks":         r.remarks or "",
        })

    if _wants_csv(request):
        headers = [
            "record_id","asset_id","asset_tag","asset_category","brand","model_name",
            "employee_id","employee_name","employee_email","quantity_issued","status",
            "issued_by","issued_date","return_date","remarks",
        ]
        return _csv_response("asset_issue_return_history", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":       "Asset Issue / Return History",
        "generated_at": timezone.now().isoformat(),
        "total":        paginated["total"],
        "total_pages":  paginated["total_pages"],
        "page":         paginated["page"],
        "limit":        paginated["limit"],
        "has_next":     paginated["has_next"],
        "has_prev":     paginated["has_prev"],
        "records":      paginated["data"],
    })


@require_http_methods(["GET"])
@jwt_required
def report_currently_issued_assets(request):
    records = AssetDetails.objects.select_related("asset", "user", "issued_by").filter(status="ISSUED")

    rows = []
    for r in records:
        days_held = (timezone.now().date() - r.created_at.date()).days
        rows.append({
            "record_id":       r.id,
            "asset_tag":       r.asset.asset_tag if r.asset else "",
            "category":        r.asset.category if r.asset else "",
            "brand":           r.asset.brand if r.asset else "",
            "model_name":      r.asset.model_name if r.asset else "",
            "employee_id":     r.user.id,
            "employee_name":   r.user.name,
            "employee_email":  r.user.email,
            "quantity_issued": r.quantity_issued,
            "issued_date":     r.created_at.isoformat(),
            "days_held":       days_held,
            "issued_by":       r.issued_by.name if r.issued_by else "",
        })

    if _wants_csv(request):
        headers = [
            "record_id","asset_tag","category","brand","model_name",
            "employee_id","employee_name","employee_email",
            "quantity_issued","issued_date","days_held","issued_by",
        ]
        return _csv_response("currently_issued_assets", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":       "Currently Issued Assets",
        "generated_at": timezone.now().isoformat(),
        "total":        paginated["total"],
        "total_pages":  paginated["total_pages"],
        "page":         paginated["page"],
        "limit":        paginated["limit"],
        "has_next":     paginated["has_next"],
        "has_prev":     paginated["has_prev"],
        "records":      paginated["data"],
    })


@require_http_methods(["GET"])
@jwt_required
def report_low_stock_assets(request):
    assets = Asset.objects.select_related("vendor").filter(status__in=["LOW_STOCK", "OUT_OF_STOCK"])

    rows = []
    for a in assets:
        rows.append({
            "asset_id":            a.id,
            "asset_tag":           a.asset_tag,
            "brand":               a.brand,
            "model_name":          a.model_name,
            "category":            a.category,
            "status":              a.status,
            "total_quantity":      a.total_quantity,
            "available_quantity":  a.available_quantity,
            "minimum_stock_level": a.minimum_stock_level,
            "vendor_name":         a.vendor.name if a.vendor else "",
        })

    if _wants_csv(request):
        headers = [
            "asset_id","asset_tag","brand","model_name","category","status",
            "total_quantity","available_quantity","minimum_stock_level","vendor_name",
        ]
        return _csv_response("low_stock_assets", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":       "Low Stock / Out of Stock Assets",
        "generated_at": timezone.now().isoformat(),
        "total":        paginated["total"],
        "total_pages":  paginated["total_pages"],
        "page":         paginated["page"],
        "limit":        paginated["limit"],
        "has_next":     paginated["has_next"],
        "has_prev":     paginated["has_prev"],
        "assets":       paginated["data"],
    })


@require_http_methods(["GET"])
@jwt_required
def report_warranty_expiry(request):
    from datetime import timedelta
    today = timezone.now().date()
    days  = int(request.GET.get("days", 0))

    assets = Asset.objects.select_related("vendor").exclude(warranty_end__isnull=True)
    if days:
        threshold = today + timedelta(days=days)
        assets = assets.filter(warranty_end__lte=threshold)
    else:
        assets = assets.filter(warranty_end__lt=today)

    rows = []
    for a in assets:
        rows.append({
            "asset_id":          a.id,
            "asset_tag":         a.asset_tag,
            "brand":             a.brand,
            "model_name":        a.model_name,
            "category":          a.category,
            "warranty_end":      a.warranty_end.isoformat(),
            "warranty_status":   a.warranty_status,
            "days_until_expiry": (a.warranty_end - today).days,
            "vendor_name":       a.vendor.name if a.vendor else "",
        })

    if _wants_csv(request):
        headers = [
            "asset_id","asset_tag","brand","model_name","category",
            "warranty_end","warranty_status","days_until_expiry","vendor_name",
        ]
        return _csv_response("warranty_expiry", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":       "Warranty Expiry Report",
        "generated_at": timezone.now().isoformat(),
        "filter_days":  days or "expired only",
        "total":        paginated["total"],
        "total_pages":  paginated["total_pages"],
        "page":         paginated["page"],
        "limit":        paginated["limit"],
        "has_next":     paginated["has_next"],
        "has_prev":     paginated["has_prev"],
        "assets":       paginated["data"],
    })


# ============================================================
# 2. TICKET & WORKFLOW REPORTS
# ============================================================

@require_http_methods(["GET"])
@jwt_required
def report_ticket_summary(request):
    from_date, to_date = _date_filters(request)
    tickets = Ticket.objects.all()
    tickets = _apply_date_range(tickets, "created_at", from_date, to_date)

    by_status       = list(tickets.values("status").annotate(count=Count("id")))
    by_type         = list(tickets.values("ticket_type").annotate(count=Count("id")))
    by_role         = list(tickets.values("created_by_role").annotate(count=Count("id")))
    by_current_role = list(
        tickets.exclude(current_role__isnull=True)
        .values("current_role").annotate(count=Count("id"))
    )

    if _wants_csv(request):
        rows = []
        for r in by_status:
            rows.append({"group": "by_status",          "key": r["status"],          "count": r["count"]})
        for r in by_type:
            rows.append({"group": "by_ticket_type",     "key": r["ticket_type"],     "count": r["count"]})
        for r in by_role:
            rows.append({"group": "by_created_by_role", "key": r["created_by_role"], "count": r["count"]})
        for r in by_current_role:
            rows.append({"group": "pending_by_role",    "key": r["current_role"],    "count": r["count"]})
        rows.append({"group": "TOTAL", "key": "total_tickets", "count": tickets.count()})
        return _csv_response("ticket_summary", ["group", "key", "count"], rows)

    return JsonResponse({
        "report":             "Ticket Summary",
        "generated_at":       timezone.now().isoformat(),
        "date_range":         {"from": from_date, "to": to_date},
        "total_tickets":      tickets.count(),
        "by_status":          by_status,
        "by_ticket_type":     by_type,
        "by_created_by_role": by_role,
        "pending_by_role":    by_current_role,
    })


@require_http_methods(["GET"])
@jwt_required
def report_ticket_full_list(request):
    from_date, to_date = _date_filters(request)
    status      = request.GET.get("status")
    ticket_type = request.GET.get("ticket_type")
    employee_id = request.GET.get("employee_id")

    tickets = Ticket.objects.select_related("employee", "assigned_to", "workflow").all()
    if status:
        tickets = tickets.filter(status__iexact=status)
    if ticket_type:
        tickets = tickets.filter(ticket_type__iexact=ticket_type)
    if employee_id:
        tickets = tickets.filter(employee_id=employee_id)
    tickets = _apply_date_range(tickets, "created_at", from_date, to_date)

    rows = []
    for t in tickets:
        rows.append({
            "ticket_id":       t.id,
            "title":           t.title,
            "ticket_type":     t.ticket_type,
            "status":          t.status,
            "priority":        t.priority or "",
            "created_by_role": t.created_by_role,
            "current_role":    t.current_role or "",
            "current_step":    t.current_step,
            "employee_id":     t.employee.id,
            "employee_name":   t.employee.name,
            "employee_email":  t.employee.email,
            "assigned_to":     t.assigned_to.name if t.assigned_to else "",
            "workflow_id":     t.workflow.id if t.workflow else "",
            "created_at":      t.created_at.isoformat(),
            "updated_at":      t.updated_at.isoformat(),
        })

    if _wants_csv(request):
        headers = [
            "ticket_id","title","ticket_type","status","priority","created_by_role",
            "current_role","current_step","employee_id","employee_name",
            "employee_email","assigned_to","workflow_id","created_at","updated_at",
        ]
        return _csv_response("ticket_full_list", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":       "Full Ticket List",
        "generated_at": timezone.now().isoformat(),
        "total":        paginated["total"],
        "total_pages":  paginated["total_pages"],
        "page":         paginated["page"],
        "limit":        paginated["limit"],
        "has_next":     paginated["has_next"],
        "has_prev":     paginated["has_prev"],
        "tickets":      paginated["data"],
    })


@require_http_methods(["GET"])
@jwt_required
def report_ticket_approval_history(request):
    from_date, to_date = _date_filters(request)
    ticket_id = request.GET.get("ticket_id")
    role      = request.GET.get("role")
    status    = request.GET.get("status")

    history = AssignedTicket.objects.select_related("ticket", "assigned_to").all()
    if ticket_id:
        history = history.filter(ticket_id=ticket_id)
    if role:
        history = history.filter(role__iexact=role)
    if status:
        history = history.filter(status__iexact=status)
    history = _apply_date_range(history, "action_date", from_date, to_date)

    rows = []
    for h in history:
        rows.append({
            "history_id":        h.id,
            "ticket_id":         h.ticket.id,
            "ticket_title":      h.ticket.title,
            "ticket_type":       h.ticket.ticket_type,
            "role":              h.role,
            "action":            h.status,
            "remarks":           h.remarks or "",
            "actioned_by_id":    h.assigned_to.id,
            "actioned_by_name":  h.assigned_to.name,
            "actioned_by_email": h.assigned_to.email,
            "action_date":       h.action_date.isoformat(),
        })

    if _wants_csv(request):
        headers = [
            "history_id","ticket_id","ticket_title","ticket_type","role","action",
            "remarks","actioned_by_id","actioned_by_name","actioned_by_email","action_date",
        ]
        return _csv_response("ticket_approval_history", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":       "Ticket Approval / Rejection History",
        "generated_at": timezone.now().isoformat(),
        "total":        paginated["total"],
        "total_pages":  paginated["total_pages"],
        "page":         paginated["page"],
        "limit":        paginated["limit"],
        "has_next":     paginated["has_next"],
        "has_prev":     paginated["has_prev"],
        "history":      paginated["data"],
    })


@require_http_methods(["GET"])
@jwt_required
def report_sla_breach(request):
    now      = timezone.now()
    breached = Ticket.objects.filter(
        step_deadline__lt=now
    ).exclude(status__in=["COMPLETED", "REJECTED"]).select_related("employee", "assigned_to")

    rows = []
    for t in breached:
        overdue_hours = round((now - t.step_deadline).total_seconds() / 3600, 1)
        rows.append({
            "ticket_id":        t.id,
            "title":            t.title,
            "ticket_type":      t.ticket_type,
            "status":           t.status,
            "priority":         t.priority or "",
            "current_role":     t.current_role or "",
            "step_deadline":    t.step_deadline.isoformat(),
            "overdue_by_hours": overdue_hours,
            "employee_id":      t.employee.id,
            "employee_name":    t.employee.name,
            "assigned_to":      t.assigned_to.name if t.assigned_to else "",
            "created_at":       t.created_at.isoformat(),
        })

    if _wants_csv(request):
        headers = [
            "ticket_id","title","ticket_type","status","priority","current_role",
            "step_deadline","overdue_by_hours","employee_id","employee_name",
            "assigned_to","created_at",
        ]
        return _csv_response("sla_breach", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":         "SLA Breach Report",
        "generated_at":   timezone.now().isoformat(),
        "total_breached": paginated["total"],
        "total_pages":    paginated["total_pages"],
        "page":           paginated["page"],
        "limit":          paginated["limit"],
        "has_next":       paginated["has_next"],
        "has_prev":       paginated["has_prev"],
        "tickets":        paginated["data"],
    })


@require_http_methods(["GET"])
@jwt_required
def report_pending_tickets_by_role(request):
    pending = list(
        Ticket.objects.exclude(status__in=["COMPLETED", "REJECTED"])
        .exclude(current_role__isnull=True)
        .values("current_role").annotate(count=Count("id"))
    )

    if _wants_csv(request):
        rows = [{"current_role": r["current_role"], "pending_count": r["count"]} for r in pending]
        return _csv_response("pending_tickets_by_role", ["current_role", "pending_count"], rows)

    return JsonResponse({
        "report":          "Pending Tickets by Role",
        "generated_at":    timezone.now().isoformat(),
        "pending_by_role": pending,
    })


# ============================================================
# 3. USER & EMPLOYEE REPORTS
# ============================================================

# @require_http_methods(["GET"])
# @jwt_required
# def report_user_summary(request):
#     users     = User.objects.all()
#     by_role   = list(users.values("role").annotate(count=Count("id")))
#     by_status = list(users.values("employment_status").annotate(count=Count("id")))
#     active    = users.filter(is_active=True, employment_status="ACTIVE").count()
#     inactive  = users.filter(is_active=False).count()

#     if _wants_csv(request):
#         rows = []
#         for r in by_role:
#             rows.append({"group": "by_role",              "key": r["role"],              "count": r["count"]})
#         for r in by_status:
#             rows.append({"group": "by_employment_status", "key": r["employment_status"], "count": r["count"]})
#         rows.append({"group": "TOTAL", "key": "total_users",       "count": users.count()})
#         rows.append({"group": "TOTAL", "key": "active_accounts",   "count": active})
#         rows.append({"group": "TOTAL", "key": "inactive_accounts", "count": inactive})
#         return _csv_response("user_summary", ["group", "key", "count"], rows)

#     return JsonResponse({
#         "report":               "User Summary",
#         "generated_at":         timezone.now().isoformat(),
#         "total_users":          users.count(),
#         "active_accounts":      active,
#         "inactive_accounts":    inactive,
#         "by_role":              by_role,
#         "by_employment_status": by_status,
#     })


@require_http_methods(["GET"])
@jwt_required
def report_user_summary(request):
    users      = User.objects.all()
    by_role    = list(users.values("role").annotate(count=Count("id")))
    by_status  = list(users.values("employment_status").annotate(count=Count("id")))
    active     = users.filter(employment_status="ACTIVE").count()
    onboarding = users.filter(employment_status="ONBOARDING").count()
    inactive   = users.filter(employment_status="EXITED").count()

    if _wants_csv(request):
        rows = []
        for r in by_role:
            rows.append({"group": "by_role",              "key": r["role"],              "count": r["count"]})
        for r in by_status:
            rows.append({"group": "by_employment_status", "key": r["employment_status"], "count": r["count"]})
        rows.append({"group": "TOTAL", "key": "total_users",         "count": users.count()})
        rows.append({"group": "TOTAL", "key": "active_accounts",     "count": active})
        rows.append({"group": "TOTAL", "key": "onboarding_accounts", "count": onboarding})
        rows.append({"group": "TOTAL", "key": "inactive_accounts",   "count": inactive})
        return _csv_response("user_summary", ["group", "key", "count"], rows)

    return JsonResponse({
        "report":               "User Summary",
        "generated_at":         timezone.now().isoformat(),
        "total_users":          users.count(),
        "active_accounts":      active,
        "onboarding_accounts":  onboarding,
        "inactive_accounts":    inactive,
        "by_role":              by_role,
        "by_employment_status": by_status,
    })

@require_http_methods(["GET"])
@jwt_required
def report_employee_asset_history(request, employee_id):
    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    records            = AssetDetails.objects.select_related("asset", "issued_by").filter(user=employee)
    currently_assigned = Asset.objects.filter(assigned_to=employee)

    rows = []
    for r in records:
        rows.append({
            "type":            "ISSUE_RECORD",
            "record_id":       r.id,
            "asset_tag":       r.asset.asset_tag if r.asset else "",
            "category":        r.asset.category if r.asset else "",
            "brand":           r.asset.brand if r.asset else "",
            "model_name":      r.asset.model_name if r.asset else "",
            "quantity_issued": r.quantity_issued,
            "status":          r.status,
            "issued_by":       r.issued_by.name if r.issued_by else "",
            "issued_date":     r.created_at.isoformat(),
            "return_date":     r.return_date.isoformat() if r.return_date else "",
            "remarks":         r.remarks or "",
        })
    for a in currently_assigned:
        rows.append({
            "type":            "ASSIGNED",
            "record_id":       a.id,
            "asset_tag":       a.asset_tag,
            "category":        a.category,
            "brand":           a.brand,
            "model_name":      a.model_name,
            "quantity_issued": "",
            "status":          "ASSIGNED",
            "issued_by":       "",
            "issued_date":     a.assigned_date.isoformat() if a.assigned_date else "",
            "return_date":     "",
            "remarks":         "",
        })

    if _wants_csv(request):
        headers = [
            "type","record_id","asset_tag","category","brand","model_name",
            "quantity_issued","status","issued_by","issued_date","return_date","remarks",
        ]
        return _csv_response(f"employee_{employee_id}_asset_history", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":               "Employee Asset History",
        "generated_at":         timezone.now().isoformat(),
        "employee_id":          employee.id,
        "employee_name":        employee.name,
        "employee_email":       employee.email,
        "role":                 employee.role,
        "employment_status":    employee.employment_status,
        "join_date":            employee.join_date.isoformat() if employee.join_date else None,
        "exit_date":            employee.exit_date.isoformat() if employee.exit_date else None,
        "total":                paginated["total"],
        "total_pages":          paginated["total_pages"],
        "page":                 paginated["page"],
        "limit":                paginated["limit"],
        "has_next":             paginated["has_next"],
        "has_prev":             paginated["has_prev"],
        "issue_return_history": paginated["data"],
    })


@require_http_methods(["GET"])
@jwt_required
def report_offboarding_checklist(request, employee_id):
    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    open_issue_records = AssetDetails.objects.select_related("asset").filter(user=employee, status="ISSUED")
    directly_assigned  = Asset.objects.filter(assigned_to=employee)
    open_tickets       = Ticket.objects.filter(employee=employee).exclude(status__in=["COMPLETED", "REJECTED"])

    rows = []
    for r in open_issue_records:
        rows.append({
            "type":            "UNRETURNED_ASSET",
            "id":              r.id,
            "asset_tag":       r.asset.asset_tag if r.asset else "",
            "category":        r.asset.category if r.asset else "",
            "quantity_issued": r.quantity_issued,
            "detail":          r.created_at.isoformat(),
        })
    for a in directly_assigned:
        rows.append({
            "type":            "DIRECTLY_ASSIGNED",
            "id":              a.id,
            "asset_tag":       a.asset_tag,
            "category":        a.category,
            "quantity_issued": "",
            "detail":          "",
        })
    for t in open_tickets:
        rows.append({
            "type":            "OPEN_TICKET",
            "id":              t.id,
            "asset_tag":       "",
            "category":        t.ticket_type,
            "quantity_issued": "",
            "detail":          t.title,
        })

    is_clear = len(rows) == 0

    if _wants_csv(request):
        summary_row = [{"type": f"OFFBOARDING_CLEAR={is_clear}", "id": "", "asset_tag": "", "category": "", "quantity_issued": "", "detail": ""}]
        headers = ["type","id","asset_tag","category","quantity_issued","detail"]
        return _csv_response(f"offboarding_checklist_employee_{employee_id}", headers, summary_row + rows)

    return JsonResponse({
        "report":            "Offboarding Checklist",
        "generated_at":      timezone.now().isoformat(),
        "employee_id":       employee.id,
        "employee_name":     employee.name,
        "employment_status": employee.employment_status,
        "offboarding_clear": is_clear,
        "unreturned_issued_assets": [r for r in rows if r["type"] == "UNRETURNED_ASSET"],
        "directly_assigned_assets": [r for r in rows if r["type"] == "DIRECTLY_ASSIGNED"],
        "open_tickets":             [r for r in rows if r["type"] == "OPEN_TICKET"],
        "summary": {
            "unreturned_asset_records": open_issue_records.count(),
            "directly_assigned_assets": directly_assigned.count(),
            "open_tickets":             open_tickets.count(),
        }
    })


@require_http_methods(["GET"])
@jwt_required
def report_exited_employees(request):
    exited = User.objects.filter(employment_status="EXITED")

    rows = []
    for u in exited:
        rows.append({
            "employee_id": u.id,
            "name":        u.name,
            "email":       u.email,
            "role":        u.role,
            "join_date":   u.join_date.isoformat() if u.join_date else "",
            "exit_date":   u.exit_date.isoformat() if u.exit_date else "",
            "is_active":   u.is_active,
        })

    if _wants_csv(request):
        headers = ["employee_id","name","email","role","join_date","exit_date","is_active"]
        return _csv_response("exited_employees", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":       "Exited Employees",
        "generated_at": timezone.now().isoformat(),
        "total":        paginated["total"],
        "total_pages":  paginated["total_pages"],
        "page":         paginated["page"],
        "limit":        paginated["limit"],
        "has_next":     paginated["has_next"],
        "has_prev":     paginated["has_prev"],
        "employees":    paginated["data"],
    })


# ============================================================
# 4. PURCHASE & FINANCE REPORTS
# ============================================================

@require_http_methods(["GET"])
@jwt_required
def report_purchase_summary(request):
    from_date, to_date = _date_filters(request)
    prs = PurchaseRequest.objects.all()
    prs = _apply_date_range(prs, "created_at", from_date, to_date)

    by_status    = list(prs.values("status").annotate(count=Count("id")))
    by_type      = list(prs.values("request_type").annotate(count=Count("id")))
    by_triggered = list(prs.values("triggered_by").annotate(count=Count("id")))

    if _wants_csv(request):
        rows = []
        for r in by_status:
            rows.append({"group": "by_status",       "key": r["status"],       "count": r["count"]})
        for r in by_type:
            rows.append({"group": "by_request_type", "key": r["request_type"], "count": r["count"]})
        for r in by_triggered:
            rows.append({"group": "by_triggered_by", "key": r["triggered_by"], "count": r["count"]})
        rows.append({"group": "TOTAL", "key": "total_requests", "count": prs.count()})
        return _csv_response("purchase_summary", ["group", "key", "count"], rows)

    return JsonResponse({
        "report":          "Purchase Request Summary",
        "generated_at":    timezone.now().isoformat(),
        "date_range":      {"from": from_date, "to": to_date},
        "total_requests":  prs.count(),
        "by_status":       by_status,
        "by_request_type": by_type,
        "by_triggered_by": by_triggered,
    })


@require_http_methods(["GET"])
@jwt_required
def report_purchase_full_list(request):
    from_date, to_date = _date_filters(request)
    status = request.GET.get("status")

    prs = PurchaseRequest.objects.select_related("asset", "created_by").all()
    if status:
        prs = prs.filter(status__iexact=status)
    prs = _apply_date_range(prs, "created_at", from_date, to_date)

    rows = []
    for pr in prs:
        rows.append({
            "request_id":         pr.id,
            "asset_id":           pr.asset.id if pr.asset else "",
            "asset_tag":          pr.asset.asset_tag if pr.asset else "",
            "asset_name":         pr.asset.model_name if pr.asset else "",
            "asset_category":     pr.asset.category if pr.asset else "",
            "request_type":       pr.request_type,
            "triggered_by":       pr.triggered_by,
            "created_by":         pr.created_by.name if pr.created_by else "",
            "quantity_needed":    pr.quantity_needed,
            "status":             pr.status,
            "remarks":            pr.remarks or "",
            "invoice_attachment": pr.invoice_attachment.url if pr.invoice_attachment else "",
            "created_at":         pr.created_at.isoformat(),
            "updated_at":         pr.updated_at.isoformat(),
        })

    if _wants_csv(request):
        headers = [
            "request_id","asset_id","asset_tag","asset_name","asset_category",
            "request_type","triggered_by","created_by","quantity_needed","status",
            "remarks","invoice_attachment","created_at","updated_at",
        ]
        return _csv_response("purchase_full_list", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":            "Full Purchase Request List",
        "generated_at":      timezone.now().isoformat(),
        "total":              paginated["total"],
        "total_pages":        paginated["total_pages"],
        "page":               paginated["page"],
        "limit":              paginated["limit"],
        "has_next":           paginated["has_next"],
        "has_prev":           paginated["has_prev"],
        "purchase_requests":  paginated["data"],
    })


@require_http_methods(["GET"])
@jwt_required
def report_vendor_summary(request):
    vendors = Vendor.objects.all()

    rows = []
    for v in vendors:
        asset_count = Asset.objects.filter(vendor=v).count()
        total_spend = Asset.objects.filter(
            vendor=v
        ).aggregate(total=Sum("purchase_price"))["total"] or 0

        rows.append({
            "vendor_id":              v.id,
            "name":                   v.name,
            "contact_person":         v.contact_person or "",
            "phone":                  v.phone or "",
            "email":                  v.email or "",
            "gst_number":             v.gst_number or "",
            "total_assets_purchased": asset_count,
            "total_spend":            float(total_spend),
        })

    if _wants_csv(request):
        headers = [
            "vendor_id","name","contact_person","phone","email",
            "gst_number","total_assets_purchased","total_spend",
        ]
        return _csv_response("vendor_summary", headers, rows)

    paginated = _paginate(request, rows)
    return JsonResponse({
        "report":        "Vendor Summary",
        "generated_at":  timezone.now().isoformat(),
        "total_vendors":  paginated["total"],
        "total_pages":   paginated["total_pages"],
        "page":          paginated["page"],
        "limit":         paginated["limit"],
        "has_next":      paginated["has_next"],
        "has_prev":      paginated["has_prev"],
        "vendors":       paginated["data"],
    })


# ============================================================
# 5. AUDIT LOG
# ============================================================

@require_http_methods(["GET"])
@jwt_required
def report_audit_log(request):
    from_date, to_date = _date_filters(request)

    asset_records  = AssetDetails.objects.select_related("asset", "user", "issued_by").all()
    asset_records  = _apply_date_range(asset_records, "created_at", from_date, to_date)
    ticket_history = AssignedTicket.objects.select_related("ticket", "assigned_to").all()
    ticket_history = _apply_date_range(ticket_history, "action_date", from_date, to_date)

    events = []

    for r in asset_records:
        events.append({
            "event_type":        "ASSET",
            "action":            r.status,
            "timestamp":         r.created_at.isoformat(),
            "actor":             r.issued_by.name if r.issued_by else "System",
            "actor_email":       r.issued_by.email if r.issued_by else "",
            "target_user":       r.user.name,
            "target_user_email": r.user.email,
            "detail":            f"Asset {r.asset.asset_tag if r.asset else 'N/A'} ({r.asset.category if r.asset else ''}) — Qty: {r.quantity_issued}",
            "remarks":           r.remarks or "",
        })

    for h in ticket_history:
        events.append({
            "event_type":        "TICKET",
            "action":            h.status,
            "timestamp":         h.action_date.isoformat(),
            "actor":             h.assigned_to.name,
            "actor_email":       h.assigned_to.email,
            "target_user":       h.ticket.employee.name if h.ticket.employee else "",
            "target_user_email": h.ticket.employee.email if h.ticket.employee else "",
            "detail":            f"Ticket #{h.ticket.id}: {h.ticket.title} — Role: {h.role}",
            "remarks":           h.remarks or "",
        })

    events.sort(key=lambda x: x["timestamp"], reverse=True)

    if _wants_csv(request):
        headers = [
            "event_type","action","timestamp","actor","actor_email",
            "target_user","target_user_email","detail","remarks",
        ]
        return _csv_response("master_audit_log", headers, events)

    paginated = _paginate(request, events)
    return JsonResponse({
        "report":       "Master Audit Log",
        "generated_at": timezone.now().isoformat(),
        "date_range":   {"from": from_date, "to": to_date},
        "total_events":  paginated["total"],
        "total_pages":   paginated["total_pages"],
        "page":          paginated["page"],
        "limit":         paginated["limit"],
        "has_next":      paginated["has_next"],
        "has_prev":      paginated["has_prev"],
        "events":        paginated["data"],
    })


# ============================================================
# 6. DASHBOARD STATS
# ============================================================

@require_http_methods(["GET"])
@jwt_required
def report_dashboard_stats(request):
    now = timezone.now()

    total_assets     = Asset.objects.count()
    available_assets = Asset.objects.filter(status="AVAILABLE").count()
    issued_assets    = Asset.objects.filter(status="ISSUED").count()
    low_stock        = Asset.objects.filter(status__in=["LOW_STOCK", "OUT_OF_STOCK"]).count()

    total_tickets = Ticket.objects.count()
    open_tickets  = Ticket.objects.exclude(status__in=["COMPLETED", "REJECTED"]).count()
    completed     = Ticket.objects.filter(status="COMPLETED").count()
    rejected      = Ticket.objects.filter(status="REJECTED").count()
    sla_breached  = Ticket.objects.filter(
        step_deadline__lt=now
    ).exclude(status__in=["COMPLETED", "REJECTED"]).count()

    total_users  = User.objects.count()
    active_users = User.objects.filter(is_active=True, employment_status="ACTIVE").count()
    onboarding   = User.objects.filter(employment_status="ONBOARDING").count()
    offboarding  = User.objects.filter(employment_status="OFFBOARDING").count()
    exited       = User.objects.filter(employment_status="EXITED").count()

    pending_purchases = PurchaseRequest.objects.filter(
        status__in=["PENDING_FINANCE", "APPROVED_FINANCE", "APPROVED_HR"]
    ).count()

    if _wants_csv(request):
        rows = [
            {"section": "assets",    "metric": "total",               "value": total_assets},
            {"section": "assets",    "metric": "available",           "value": available_assets},
            {"section": "assets",    "metric": "issued",              "value": issued_assets},
            {"section": "assets",    "metric": "low_or_out_of_stock", "value": low_stock},
            {"section": "tickets",   "metric": "total",               "value": total_tickets},
            {"section": "tickets",   "metric": "open",                "value": open_tickets},
            {"section": "tickets",   "metric": "completed",           "value": completed},
            {"section": "tickets",   "metric": "rejected",            "value": rejected},
            {"section": "tickets",   "metric": "sla_breached",        "value": sla_breached},
            {"section": "users",     "metric": "total",               "value": total_users},
            {"section": "users",     "metric": "active",              "value": active_users},
            {"section": "users",     "metric": "onboarding",          "value": onboarding},
            {"section": "users",     "metric": "offboarding",         "value": offboarding},
            {"section": "users",     "metric": "exited",              "value": exited},
            {"section": "purchases", "metric": "pending_approval",    "value": pending_purchases},
        ]
        return _csv_response("dashboard_stats", ["section", "metric", "value"], rows)

    return JsonResponse({
        "report":       "Dashboard Stats",
        "generated_at": now.isoformat(),
        "assets":    {"total": total_assets,   "available": available_assets,  "issued": issued_assets,   "low_or_out_of_stock": low_stock},
        "tickets":   {"total": total_tickets,  "open": open_tickets,           "completed": completed,    "rejected": rejected, "sla_breached": sla_breached},
        "users":     {"total": total_users,    "active": active_users,         "onboarding": onboarding,  "offboarding": offboarding, "exited": exited},
        "purchases": {"pending_approval": pending_purchases},
    })