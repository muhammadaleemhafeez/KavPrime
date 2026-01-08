# Tickets/tasks.py
from celery import shared_task
from django.utils import timezone

from .models import Ticket
from .services import add_history, notify, get_first_by_role, approve


@shared_task
def escalate_overdue_tickets():
    now = timezone.now()
    count = 0

    # 1) NEW workflow-based overdue
    wf_overdue = Ticket.objects.filter(
        workflow__isnull=False,
        current_step__gt=0,
        step_deadline__isnull=False,
        step_deadline__lte=now,
        status__startswith="PENDING_"
    ).select_related("employee", "workflow")

    for ticket in wf_overdue:
        try:
            # Auto move to next step by "approving" system user not available
            # We'll just notify SENIOR_PMO or the current role's supervisor.
            senior = get_first_by_role("SENIOR_PMO")
            if senior and getattr(senior, "email", None):
                notify(
                    senior.email,
                    f"Overdue Ticket #{ticket.id}",
                    f"Ticket is overdue at role: {ticket.current_role}. Please review/escalate."
                )
                count += 1
        except Exception:
            continue

    # 2) OLD TEAM_PMO SLA overdue (your existing logic)
    old_overdue = Ticket.objects.filter(
        status="PENDING_TEAM_PMO",
        team_pmo_deadline__isnull=False,
        team_pmo_deadline__lte=now
    ).select_related("employee")

    senior = get_first_by_role("SENIOR_PMO")
    for ticket in old_overdue:
        try:
            if not senior:
                continue

            ticket.status = "PENDING_SENIOR_PMO"
            ticket.team_pmo_deadline = None
            ticket.save(update_fields=["status", "team_pmo_deadline"])

            add_history(
                ticket=ticket,
                assigned_to=senior,
                role="SENIOR_PMO",
                status="ESCALATED",
                remarks="Auto escalated after SLA timeout (TEAM_PMO no action)."
            )

            notify(
                senior.email,
                f"Ticket #{ticket.id} escalated to you",
                "TEAM_PMO did not act within SLA. Ticket is now pending your action."
            )

            if getattr(ticket.employee, "email", None):
                notify(
                    ticket.employee.email,
                    f"Ticket #{ticket.id} escalated",
                    "Your ticket moved to Senior PMO due to SLA timeout."
                )

            count += 1
        except Exception:
            continue

    return f"Handled {count} overdue tickets"
