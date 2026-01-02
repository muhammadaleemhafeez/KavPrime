import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Ticket
from users.models import User
from django.utils import timezone
from .models import AssignedTicket


@csrf_exempt
def create_ticket(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    employee_id = data.get("employee_id")
    ticket_type = data.get("ticket_type")
    title = data.get("title")
    description = data.get("description")

    if not employee_id or not ticket_type or not title or not description:
        return JsonResponse({"error": "employee_id, ticket_type, title, description are required"}, status=400)

    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    # Create ticket
    ticket = Ticket.objects.create(
        employee=employee,
        ticket_type=ticket_type,
        title=title,
        description=description,
        status="PENDING_TEAM_PMO",
        created_by_role=employee.role,
        team_pmo_deadline=timezone.now() + timezone.timedelta(hours=2)  # example SLA
    )

    # Assign to TEAM_PMO automatically (first TEAM_PMO user)
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
        # If no TEAM_PMO exists, still log creation event
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


def ticket_history(request, ticket_id):
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)

    history = AssignedTicket.objects.filter(ticket_id=ticket_id).order_by("action_date").values(
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
