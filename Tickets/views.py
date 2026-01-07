import json
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Ticket, AssignedTicket
from users.models import User

from .services import notify, get_emails_by_role


@csrf_exempt
def create_ticket(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    # ✅ request.body is bytes, decode it properly
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    employee_id = data.get("employee_id")
    ticket_type = data.get("ticket_type")
    title = data.get("title")
    description = data.get("description")

    if not employee_id or not ticket_type or not title or not description:
        return JsonResponse(
            {"error": "employee_id, ticket_type, title, description are required"},
            status=400
        )

    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    # ✅ Create ticket with 4-hour SLA for TEAM_PMO action
    ticket = Ticket.objects.create(
        employee=employee,
        ticket_type=ticket_type,
        title=title,
        description=description,
        status="PENDING_TEAM_PMO",
        created_by_role=employee.role,
        team_pmo_deadline=timezone.now() + timedelta(hours=4)  # ✅ 4 hours
    )

    # ✅ Assign to TEAM_PMO automatically (first TEAM_PMO user)
    team_pmo = User.objects.filter(role="TEAM_PMO").first()

    if team_pmo:
        AssignedTicket.objects.create(
            ticket=ticket,
            assigned_to=team_pmo,
            role="TEAM_PMO",
            status="ASSIGNED",
            remarks="Auto assigned on ticket creation",
            action_date=timezone.now()
        )
    else:
        # ✅ If no TEAM_PMO exists, still log creation event
        AssignedTicket.objects.create(
            ticket=ticket,
            assigned_to=employee,
            role="EMPLOYEE",
            status="ASSIGNED",
            remarks="Ticket created but no TEAM_PMO user found",
            action_date=timezone.now()
        )

    return JsonResponse({
        "message": "Ticket created successfully",
        "ticket_id": ticket.id
    }, status=201)


def list_tickets(request):
    tickets = Ticket.objects.all().values(
        "id",
        "employee_id",
        "ticket_type",
        "title",
        "description",
        "status",
        "created_at"
    )

    return JsonResponse(list(tickets), safe=False)



@csrf_exempt
def update_ticket_status(request):
    if request.method != "PUT":
        return JsonResponse({"error": "PUT method required"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    employee_id = data.get("employee_id")
    new_status = data.get("status")

    if not employee_id or not new_status:
        return JsonResponse({"error": "employee_id and status are required"}, status=400)

    # Check if employee exists
    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    # Update all tickets of this employee
    tickets = Ticket.objects.filter(employee=employee)
    if not tickets.exists():
        return JsonResponse({"error": "No tickets found for this employee"}, status=404)

    # Validate the new status
    valid_statuses = [choice[0] for choice in Ticket.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return JsonResponse({"error": f"Invalid status. Valid statuses are {valid_statuses}"}, status=400)

    tickets.update(status=new_status)

    return JsonResponse({
        "message": f"Status updated to '{new_status}' for {tickets.count()} ticket(s)"
    }, status=200)

from django.http import JsonResponse
from .models import AssignedTicket

def ticket_history(request, employee_id):
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)

    history = AssignedTicket.objects.filter(
        assigned_to_id=employee_id
    ).order_by("action_date").values(
        "id",
        "ticket_id",
        "assigned_to_id",
        "role",
        "status",
        "remarks",
        "action_date",
    )

    return JsonResponse(list(history), safe=False)



def escalate_ticket(request, ticket_id):
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)

    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    # Only allow escalation from TEAM_PMO -> SENIOR_PMO
    if ticket.status != "PENDING_TEAM_PMO":
        return JsonResponse({"error": f"Ticket is not in PENDING_TEAM_PMO. Current: {ticket.status}"}, status=400)

    senior = User.objects.filter(role="SENIOR_PMO").first()
    if not senior:
        return JsonResponse({"error": "No SENIOR_PMO user found"}, status=400)

    ticket.status = "PENDING_SENIOR_PMO"
    ticket.team_pmo_deadline = None
    ticket.save()

    AssignedTicket.objects.create(
        ticket=ticket,
        assigned_to=senior,
        role="SENIOR_PMO",
        status="ESCALATED",
        remarks="Manually escalated via API",
        action_date=timezone.now()
    )

    return JsonResponse({
        "message": f"Ticket #{ticket.id} escalated to SENIOR_PMO",
        "ticket_id": ticket.id,
        "new_status": ticket.status,
        "assigned_to": senior.id
    }, status=200)

# team_pmo action regarding email below code 

@csrf_exempt
def team_pmo_action(request, ticket_id):
    """
    POST JSON:
    { "action": "APPROVE" }
    OR
    { "action": "REJECT", "reason": "Not allowed" }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    action = (data.get("action") or "").upper()
    reason = data.get("reason", "")

    try:
        ticket = Ticket.objects.select_related("employee").get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    if ticket.status != "PENDING_TEAM_PMO":
        return JsonResponse({"error": f"Ticket is not pending TEAM_PMO. Current: {ticket.status}"}, status=400)

    if action == "APPROVE":
        ticket.status = "PENDING_ADMIN"
        ticket.save(update_fields=["status"])

        # email to Admin
        admin_emails = get_emails_by_role("ADMIN")
        notify(
            admin_emails,
            f"Ticket Approved by TEAM_PMO (#{ticket.id})",
            f"TEAM_PMO approved ticket #{ticket.id}.\nEmployee: {ticket.employee.email}\nPlease proceed."
        )

        return JsonResponse({"message": "Ticket approved by TEAM_PMO", "new_status": ticket.status})

    if action == "REJECT":
        ticket.status = "REJECTED_BY_TEAM_PMO"
        ticket.save(update_fields=["status"])

        # email to Employee
        if getattr(ticket.employee, "email", None):
            notify(
                ticket.employee.email,
                f"Ticket Rejected (#{ticket.id})",
                f"Your ticket #{ticket.id} was rejected by TEAM_PMO.\nReason: {reason}"
            )

        return JsonResponse({"message": "Ticket rejected by TEAM_PMO", "new_status": ticket.status})

    return JsonResponse({"error": "Invalid action. Use APPROVE or REJECT"}, status=400)

# email process of admin email (PMO,hr,employee)


@csrf_exempt
def admin_complete(request, ticket_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        ticket = Ticket.objects.select_related("employee").get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    if ticket.status != "PENDING_ADMIN":
        return JsonResponse({"error": f"Ticket is not pending ADMIN. Current: {ticket.status}"}, status=400)

    ticket.status = "COMPLETED"
    ticket.save(update_fields=["status"])

    team_pmo_emails = get_emails_by_role("TEAM_PMO")
    hr_emails = get_emails_by_role("HR")
    employee_email = getattr(ticket.employee, "email", None)

    recipients = list(set(team_pmo_emails + hr_emails + ([employee_email] if employee_email else [])))

    notify(
        recipients,
        f"Ticket Completed (#{ticket.id})",
        f"Ticket #{ticket.id} has been completed and handed over.\nEmployee: {employee_email}"
    )

    return JsonResponse({"message": "Ticket completed", "new_status": ticket.status})
