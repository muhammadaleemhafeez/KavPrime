import json
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Ticket, AssignedTicket
from users.models import User
from Tickets.models import Ticket, Workflow 

# ✅ use your services engine (dynamic workflow + fallback)
from .services import route_new_ticket, approve, reject, add_history


@csrf_exempt
@require_http_methods(["POST"])
def create_ticket(request):
    """
    Employee creates a ticket:
    - Creates Ticket
    - Routes it using the workflow engine (admin-configurable)
    - Sends emails automatically inside services
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Existing fields (no change)
    employee_id = data.get("employee_id")
    ticket_type = data.get("ticket_type")
    title = data.get("title")
    description = data.get("description")

    # ✅ STEP A: Validate ticket_type (VERY IMPORTANT)
    valid_ticket_types = [choice[0] for choice in Ticket.TICKET_TYPES]
    if ticket_type not in valid_ticket_types:
        return JsonResponse({
        "error": "Invalid ticket_type",
        "allowed_ticket_types": valid_ticket_types
        }, status=400)


    # New field (assigned_to)
    assigned_to_id = data.get("assigned_to")  # New field for assigned user

    # Ensure all required fields are present
    if not employee_id or not ticket_type or not title or not description:
        return JsonResponse(
            {"error": "employee_id, ticket_type, title, description are required"},
            status=400
        )

    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    # If assigned_to is provided, get that user, otherwise leave it as null
    assigned_to = None
    if assigned_to_id:
        try:
            assigned_to = User.objects.get(id=assigned_to_id)
        except User.DoesNotExist:
            return JsonResponse({"error": "Assigned user not found"}, status=404)

    # Create the ticket
    ticket = Ticket.objects.create(
        employee=employee,
        ticket_type=ticket_type,
        title=title,
        description=description,
        assigned_to=assigned_to,  # Assign to the selected user (if any)
        status="PENDING_TEAM_PMO",  # Default, will be overwritten by workflow engine if configured
        created_by_role=employee.role_name if hasattr(employee, "role_name") else employee.role,
    )

    # Route ticket using the engine (workflow if exists, else fallback to old hardcoded logic)
    try:
        route_new_ticket(ticket)  # Using your service to handle the routing logic
        # ✅ STEP B: Refresh ticket from DB so workflow_id is visible
        ticket.refresh_from_db()
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    # Return the created ticket data (including assigned_to)
    return JsonResponse({
        "message": "Ticket created successfully",
        "ticket_id": ticket.id,
        "assigned_to": ticket.assigned_to.id if ticket.assigned_to else None,  # Return the assigned user (if any)
        "status": ticket.status,
        "current_role": ticket.current_role,
        "current_step": ticket.current_step,
        "workflow_id": ticket.workflow_id,
    }, status=201)


@require_http_methods(["GET"])
def list_tickets(request):
    tickets = Ticket.objects.all().values(
        "id",
        "employee_id",
        "ticket_type",
        "title",
        "description",
        "status",
        "created_by_role",
        "workflow_id",
        "current_step",
        "current_role",
        "created_at",
        "updated_at",
    )
    return JsonResponse(list(tickets), safe=False)


@csrf_exempt
@require_http_methods(["PUT"])
def update_ticket_status(request):
    """
    Your existing endpoint:
    Updates all tickets status for employee (kept as is)
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    employee_id = data.get("employee_id")
    new_status = data.get("status")

    if not employee_id or not new_status:
        return JsonResponse({"error": "employee_id and status are required"}, status=400)

    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    tickets = Ticket.objects.filter(employee=employee)
    if not tickets.exists():
        return JsonResponse({"error": "No tickets found for this employee"}, status=404)

    valid_statuses = [choice[0] for choice in Ticket.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return JsonResponse({"error": f"Invalid status. Valid statuses are {valid_statuses}"}, status=400)

    tickets.update(status=new_status)

    return JsonResponse({
        "message": f"Status updated to '{new_status}' for {tickets.count()} ticket(s)"
    }, status=200)


@require_http_methods(["GET"])
def ticket_history(request, employee_id):
    """
    Returns the ticket history for an employee based on assigned tickets and status changes
    URL: /api/tickets/ticket-history/<employee_id>/
    """
    # Fetch all AssignedTicket records for this employee, ordered by the action date
    history = AssignedTicket.objects.filter(assigned_to_id=employee_id).order_by("action_date").values(
        "id",
        "ticket_id",
        "assigned_to_id",
        "role",
        "status",
        "remarks",
        "action_date",
    )

    # If no history records are found for the given employee
    if not history.exists():
        return JsonResponse({"message": "No history found for this employee"}, status=200)

    # Return the list of history records as a JSON response
    return JsonResponse(list(history), safe=False, status=200)

@require_http_methods(["GET"])
def escalate_ticket(request, ticket_id):
    """
    Manual escalation endpoint (kept).
    For dynamic workflows, we simply log and notify senior (or move status).
    """
    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    # If already completed/rejected, don't escalate
    if ticket.status in ["COMPLETED", "REJECTED"]:
        return JsonResponse({"error": f"Ticket is {ticket.status}, cannot escalate."}, status=400)

    senior = User.objects.filter(role="SENIOR_PMO").first() or User.objects.filter(role_obj__name="SENIOR_PMO").first()
    if not senior:
        return JsonResponse({"error": "No SENIOR_PMO user found"}, status=400)

    # Keep your old behavior
    ticket.status = "PENDING_SENIOR_PMO"
    ticket.team_pmo_deadline = None
    ticket.save(update_fields=["status", "team_pmo_deadline"])

    add_history(
        ticket=ticket,
        assigned_to=senior,
        role="SENIOR_PMO",
        status="ESCALATED",
        remarks="Manually escalated via API"
    )

    return JsonResponse({
        "message": f"Ticket #{ticket.id} escalated to SENIOR_PMO",
        "ticket_id": ticket.id,
        "new_status": ticket.status,
        "assigned_to": senior.id
    }, status=200)


# ---------------------------
# EMAIL PROCESS ENDPOINTS
# ---------------------------

@csrf_exempt
@require_http_methods(["POST"])
def team_pmo_action(request, ticket_id):
    """
    URL: /team-pmo-action/<ticket_id>/
    Body:
      { "action": "APPROVE", "remarks": "..." }
      OR
      { "action": "REJECT", "remarks": "..." }
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    action = (data.get("action") or "").upper()
    remarks = data.get("remarks") or data.get("reason") or ""

    if action not in ["APPROVE", "REJECT"]:
        return JsonResponse({"error": "action must be APPROVE or REJECT"}, status=400)

    # For now actor is the first TEAM_PMO user
    actor = User.objects.filter(role="TEAM_PMO").first() or User.objects.filter(role_obj__name="TEAM_PMO").first()
    if not actor:
        return JsonResponse({"error": "No TEAM_PMO user found"}, status=400)

    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    # Optional check: only allow if ticket pending TEAM_PMO
    if not ticket.status.startswith("PENDING_"):
        return JsonResponse({"error": f"Ticket is not pending. Current status: {ticket.status}"}, status=400)

    try:
        if action == "APPROVE":
            approve(ticket, actor, remarks=remarks)
            return JsonResponse({"message": "Ticket approved", "ticket_id": ticket.id, "status": ticket.status})
        else:
            reject(ticket, actor, remarks=remarks)
            return JsonResponse({"message": "Ticket rejected", "ticket_id": ticket.id, "status": ticket.status})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def admin_complete(request, ticket_id):
    """
    URL: /admin-complete/<ticket_id>/
    Body: { "remarks": "Item handed over" }

    This will call approve() using ADMIN actor.
    In workflow engine:
      - if ADMIN is last step => COMPLETED
      - if not last step => moves to next (e.g. FINANCE)
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = {}

    remarks = data.get("remarks", "Completed by Admin")

    actor = User.objects.filter(role="ADMIN").first() or User.objects.filter(role_obj__name="ADMIN").first()
    if not actor:
        return JsonResponse({"error": "No ADMIN user found"}, status=400)

    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    try:
        approve(ticket, actor, remarks=remarks)
        return JsonResponse({
            "message": "Admin completed/approved step",
            "ticket_id": ticket.id,
            "status": ticket.status,
            "current_step": ticket.current_step,
            "current_role": ticket.current_role,
        }, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
