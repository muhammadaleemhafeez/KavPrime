import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Ticket
from users.models import User


@csrf_exempt
def create_ticket(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    data = json.loads(request.body)

    try:
        employee = User.objects.get(id=data.get("employee_id"))
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    ticket = Ticket.objects.create(
        employee=employee,
        ticket_type=data.get("ticket_type"),
        title=data.get("title"),
        description=data.get("description"),
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
