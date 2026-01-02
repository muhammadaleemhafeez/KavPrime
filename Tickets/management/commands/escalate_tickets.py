from django.core.management.base import BaseCommand
from django.utils import timezone
from users.models import User
from Tickets.models import Ticket, AssignedTicket
from Tickets.email_utils import send_email

from Tickets.email_utils import send_email


class Command(BaseCommand):
    help = "Auto escalate tickets from TEAM_PMO to SENIOR_PMO"

    def handle(self, *args, **kwargs):
        now = timezone.now()

        tickets = Ticket.objects.filter(
            status="PENDING_TEAM_PMO",
            escalation_deadline__lte=now
        )

        senior = User.objects.filter(role="SENIOR_PMO").first()
        if not senior:
            self.stdout.write("No SENIOR_PMO user found")
            return

        for ticket in tickets:
            ticket.status = "PENDING_SENIOR_PMO"
            ticket.save()

            AssignedTicket.objects.create(
                ticket=ticket,
                assigned_to=senior,
                role="SENIOR_PMO",
                status="ESCALATED",
                remarks="Auto escalated due to inactivity"
            )

            send_email(
                senior.email,
                f"Ticket #{ticket.id} Escalated",
                "TEAM_PMO did not act within SLA time."
            )

            send_email(
                ticket.employee.email,
                f"Ticket #{ticket.id} Escalated",
                "Your ticket has been escalated to Senior PMO."
            )

        self.stdout.write(f"Escalated {tickets.count()} tickets")
