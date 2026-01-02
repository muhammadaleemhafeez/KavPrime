from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Ticket
from .services import add_history, notify, get_first_by_role

@shared_task
def escalate_team_pmo_overdue():
    now = timezone.now()

    # Fetch tickets that are PENDING_TEAM_PMO and past their team_pmo_deadline
    overdue = Ticket.objects.filter(
        status="PENDING_TEAM_PMO",
        team_pmo_deadline__isnull=False,
        team_pmo_deadline__lte=now
    )

    # Get the first Senior PMO from your system
    senior = get_first_by_role("SENIOR_PMO")
    if not senior:
        return "No SENIOR_PMO found"

    count = 0
    for ticket in overdue:
        # Update ticket status and clear team_pmo_deadline
        ticket.status = "PENDING_SENIOR_PMO"
        ticket.team_pmo_deadline = None
        ticket.save()

        # Add history record for the ticket
        add_history(ticket, senior, "SENIOR_PMO", "ESCALATED", "Auto escalated due to SLA timeout")

        # Notify the Senior PMO and the employee about the escalation
        notify(senior.email, f"Ticket #{ticket.id} escalated to you", "TEAM_PMO did not act in time.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} escalated", "Your ticket moved to Senior PMO due to timeout.")
        
        count += 1

    return f"Escalated {count} tickets"
