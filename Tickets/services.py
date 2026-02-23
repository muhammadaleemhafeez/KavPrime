from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from .models import AssignedTicket, Workflow, WorkflowStep, Ticket

# from Tickets.models import AssignedTicket

User = get_user_model()

SLA_HOURS_FALLBACK = 4  # used if workflow step SLA not set or workflow missing


def notify(to_emails, subject, message):
    if not to_emails:
        return
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    to_emails = list({e.strip() for e in to_emails if e and str(e).strip()})
    if not to_emails:
        return

    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to_emails,
        fail_silently=False
    )


def add_history(ticket, assigned_to, role, status, remarks=""):
    AssignedTicket.objects.create(
        ticket=ticket,
        assigned_to=assigned_to,
        role=role,
        status=status,
        remarks=remarks,
        action_date=timezone.now()
    )



def get_emails_by_role(role_name: str):
    qs = User.objects.filter(is_active=True).exclude(email__isnull=True).exclude(email="")
    # Prefer dynamic role_obj, fallback to old role string
    emails = list(qs.filter(role_obj__name=role_name).values_list("email", flat=True))
    if emails:
        return emails
    return list(qs.filter(role=role_name).values_list("email", flat=True))
