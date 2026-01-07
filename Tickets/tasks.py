from celery import shared_task
from django.utils import timezone

from .models import Ticket
from .services import add_history, notify, get_first_by_role


@shared_task
def escalate_team_pmo_overdue():
    now = timezone.now()

    overdue_qs = Ticket.objects.filter(
        status="PENDING_TEAM_PMO",
        team_pmo_deadline__isnull=False,
        team_pmo_deadline__lte=now
    )

    if not overdue_qs.exists():
        return "No overdue tickets"

    senior = get_first_by_role("SENIOR_PMO")
    if not senior:
        return "No SENIOR_PMO found"

    count = 0

    for ticket in overdue_qs.select_related("employee"):
        try:
            ticket.status = "PENDING_SENIOR_PMO"
            ticket.team_pmo_deadline = None
            # If your Ticket model doesn't have updated_at, remove it from update_fields
            ticket.save(update_fields=["status", "team_pmo_deadline"])

            add_history(
                ticket=ticket,
                assigned_to=senior,
                role="SENIOR_PMO",
                status="ESCALATED",
                remarks="Auto escalated after 4 hours SLA timeout (TEAM_PMO no action)."
            )

            # Notify Senior PMO
            notify(
                senior.email,
                f"Ticket #{ticket.id} escalated to you",
                "TEAM_PMO did not act within SLA. Ticket is now pending your action."
            )

            # Notify Employee
            if getattr(ticket.employee, "email", None):
                notify(
                    ticket.employee.email,
                    f"Ticket #{ticket.id} escalated",
                    "Your ticket moved to Senior PMO due to SLA timeout."
                )

            count += 1
        except Exception:
            continue

    return f"Escalated {count} tickets"
