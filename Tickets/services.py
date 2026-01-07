from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from .models import AssignedTicket

User = get_user_model()

SLA_HOURS = 4  # change here


def notify(to_emails, subject, message):
    """
    to_emails can be a string (single email) OR a list of emails.
    """
    if not to_emails:
        return

    if isinstance(to_emails, str):
        to_emails = [to_emails]

    # clean + unique
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


def get_first_by_role(role):
    return User.objects.filter(role=role, is_active=True).order_by("id").first()


def get_emails_by_role(role):
    return list(
        User.objects.filter(role=role, is_active=True)
        .exclude(email__isnull=True)
        .exclude(email="")
        .values_list("email", flat=True)
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


def route_new_ticket(ticket):
    """
    Called right after ticket is created.
    Employee -> TEAM_PMO (deadline 4 hours)
    """
    creator_role = ticket.employee.role
    ticket.created_by_role = creator_role

    if creator_role == "EMPLOYEE":
        team = get_first_by_role("TEAM_PMO")
        if not team:
            raise ValueError("No TEAM_PMO user found")

        ticket.status = "PENDING_TEAM_PMO"
        ticket.team_pmo_deadline = timezone.now() + timedelta(hours=SLA_HOURS)
        ticket.save(update_fields=["status", "team_pmo_deadline", "created_by_role"])

        add_history(ticket, team, "TEAM_PMO", "ASSIGNED", "New ticket assigned to Team PMO")

        # ✅ email to Team PMO + employee
        notify(team.email, f"Ticket #{ticket.id} assigned to you", "A new ticket requires review.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} created", "Your ticket has been sent to Team PMO.")
        return

    # If you want other roles to create tickets, keep these blocks.
    if creator_role == "TEAM_PMO":
        senior = get_first_by_role("SENIOR_PMO")
        if not senior:
            raise ValueError("No SENIOR_PMO user found")

        ticket.status = "PENDING_SENIOR_PMO"
        ticket.team_pmo_deadline = None
        ticket.save(update_fields=["status", "team_pmo_deadline", "created_by_role"])

        add_history(ticket, senior, "SENIOR_PMO", "ASSIGNED", "Ticket created by Team PMO → assigned to Senior PMO")
        notify(senior.email, f"Ticket #{ticket.id} assigned to you", "Ticket created by Team PMO requires your review.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} created", "Your ticket has been sent to Senior PMO.")
        return

    if creator_role == "SENIOR_PMO":
        admin = get_first_by_role("ADMIN")
        if not admin:
            raise ValueError("No ADMIN user found")

        ticket.status = "PENDING_ADMIN"
        ticket.team_pmo_deadline = None
        ticket.save(update_fields=["status", "team_pmo_deadline", "created_by_role"])

        add_history(ticket, admin, "ADMIN", "ASSIGNED", "Ticket created by Senior PMO → assigned to Admin")
        notify(admin.email, f"Ticket #{ticket.id} assigned to you", "Ticket requires admin review.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} created", "Your ticket has been sent to Admin.")
        return

    raise ValueError(f"Creator role '{creator_role}' is not allowed to create tickets.")


def approve(ticket, actor, remarks=""):
    """
    TEAM_PMO approve -> ADMIN (email admin)
    SENIOR_PMO approve -> ADMIN
    ADMIN approve -> COMPLETED (final emails to TEAM_PMO + HR + employee)
    """
    if actor.role == "TEAM_PMO":
        admin = get_first_by_role("ADMIN")
        if not admin:
            raise ValueError("No ADMIN user found")

        add_history(ticket, actor, "TEAM_PMO", "APPROVED", remarks)
        add_history(ticket, admin, "ADMIN", "ASSIGNED", "Approved by Team PMO → assigned to Admin")

        ticket.status = "PENDING_ADMIN"
        ticket.team_pmo_deadline = None
        ticket.save(update_fields=["status", "team_pmo_deadline"])

        notify(admin.email, f"Ticket #{ticket.id} needs action", "Ticket approved by Team PMO.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} approved by Team PMO", "Ticket moved to Admin.")
        return

    if actor.role == "SENIOR_PMO":
        admin = get_first_by_role("ADMIN")
        if not admin:
            raise ValueError("No ADMIN user found")

        add_history(ticket, actor, "SENIOR_PMO", "APPROVED", remarks)
        add_history(ticket, admin, "ADMIN", "ASSIGNED", "Approved by Senior PMO → assigned to Admin")

        ticket.status = "PENDING_ADMIN"
        ticket.team_pmo_deadline = None
        ticket.save(update_fields=["status", "team_pmo_deadline"])

        notify(admin.email, f"Ticket #{ticket.id} needs action", "Ticket approved by Senior PMO.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} approved by Senior PMO", "Ticket moved to Admin.")
        return

    if actor.role == "ADMIN":
        add_history(ticket, actor, "ADMIN", "COMPLETED", remarks)
        ticket.status = "COMPLETED"
        ticket.save(update_fields=["status"])

        # ✅ FINAL EMAIL: Team PMO + HR + Employee
        team_pmo_emails = get_emails_by_role("TEAM_PMO")
        hr_emails = get_emails_by_role("HR")
        employee_email = getattr(ticket.employee, "email", None)

        recipients = list(set(team_pmo_emails + hr_emails + ([employee_email] if employee_email else [])))

        notify(
            recipients,
            f"Ticket #{ticket.id} completed and handed over",
            "Admin processed the request and handed over the item/service."
        )
        return

    raise ValueError("This role cannot approve tickets.")


def reject(ticket, actor, remarks=""):
    """
    Reject always notifies employee.
    """
    if actor.role not in ["TEAM_PMO", "SENIOR_PMO", "ADMIN"]:
        raise ValueError("This role cannot reject tickets.")

    add_history(ticket, actor, actor.role, "REJECTED", remarks)
    ticket.status = "REJECTED"
    ticket.team_pmo_deadline = None
    ticket.save(update_fields=["status", "team_pmo_deadline"])

    notify(ticket.employee.email, f"Ticket #{ticket.id} rejected", f"Remarks: {remarks}")
