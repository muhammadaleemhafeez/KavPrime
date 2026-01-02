from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from .models import Ticket, AssignedTicket

User = get_user_model()

SLA_HOURS = 4  # ✅ change here

def notify(email, subject, message):
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)

def get_first_by_role(role):
    return User.objects.filter(role=role, is_active=True).order_by("id").first()

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
    creator_role = ticket.employee.role
    ticket.created_by_role = creator_role

    if creator_role == "EMPLOYEE":
        team = get_first_by_role("TEAM_PMO")
        if not team:
            raise ValueError("No TEAM_PMO user found")
        ticket.status = "PENDING_TEAM_PMO"
        ticket.team_pmo_deadline = timezone.now() + timedelta(hours=SLA_HOURS)
        ticket.save()
        add_history(ticket, team, "TEAM_PMO", "ASSIGNED", "New ticket assigned to Team PMO")

        notify(team.email, f"Ticket #{ticket.id} assigned to you", "A new ticket requires review.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} created", "Your ticket has been sent to Team PMO.")

    elif creator_role == "TEAM_PMO":
        senior = get_first_by_role("SENIOR_PMO")
        if not senior:
            raise ValueError("No SENIOR_PMO user found")
        ticket.status = "PENDING_SENIOR_PMO"
        ticket.team_pmo_deadline = None
        ticket.save()
        add_history(ticket, senior, "SENIOR_PMO", "ASSIGNED", "Ticket created by Team PMO → assigned to Senior PMO")

        notify(senior.email, f"Ticket #{ticket.id} assigned to you", "Ticket created by Team PMO requires your review.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} created", "Your ticket has been sent to Senior PMO.")

    elif creator_role == "SENIOR_PMO":
        admin = get_first_by_role("ADMIN")
        if not admin:
            raise ValueError("No ADMIN user found")
        ticket.status = "PENDING_ADMIN"
        ticket.team_pmo_deadline = None
        ticket.save()
        add_history(ticket, admin, "ADMIN", "ASSIGNED", "Ticket created by Senior PMO → assigned to Admin")

        notify(admin.email, f"Ticket #{ticket.id} assigned to you", "Ticket requires inventory/admin review.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} created", "Your ticket has been sent to Admin.")

    else:
        raise ValueError(f"Creator role '{creator_role}' is not allowed to create tickets.")


def approve(ticket, actor, remarks=""):
    # TEAM_PMO approve goes to ADMIN
    # SENIOR_PMO approve goes to ADMIN
    # ADMIN approve completes

    if actor.role == "TEAM_PMO":
        admin = get_first_by_role("ADMIN")
        if not admin:
            raise ValueError("No ADMIN user found")

        add_history(ticket, actor, "TEAM_PMO", "APPROVED", remarks)
        add_history(ticket, admin, "ADMIN", "ASSIGNED", "Approved by Team PMO → assigned to Admin")

        ticket.status = "PENDING_ADMIN"
        ticket.team_pmo_deadline = None
        ticket.save()

        notify(admin.email, f"Ticket #{ticket.id} needs action", "Ticket approved by Team PMO.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} approved by Team PMO", "Ticket moved to Admin.")

    elif actor.role == "SENIOR_PMO":
        admin = get_first_by_role("ADMIN")
        if not admin:
            raise ValueError("No ADMIN user found")

        add_history(ticket, actor, "SENIOR_PMO", "APPROVED", remarks)
        add_history(ticket, admin, "ADMIN", "ASSIGNED", "Approved by Senior PMO → assigned to Admin")

        ticket.status = "PENDING_ADMIN"
        ticket.team_pmo_deadline = None
        ticket.save()

        notify(admin.email, f"Ticket #{ticket.id} needs action", "Ticket approved by Senior PMO.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} approved by Senior PMO", "Ticket moved to Admin.")

    elif actor.role == "ADMIN":
        add_history(ticket, actor, "ADMIN", "COMPLETED", remarks)
        ticket.status = "COMPLETED"
        ticket.save()

        notify(ticket.employee.email, f"Ticket #{ticket.id} completed", "Admin approved and processed your request.")

    else:
        raise ValueError("This role cannot approve tickets.")


def reject(ticket, actor, remarks=""):
    # Reject always goes back to employee (creator)
    if actor.role not in ["TEAM_PMO", "SENIOR_PMO", "ADMIN"]:
        raise ValueError("This role cannot reject tickets.")

    add_history(ticket, actor, actor.role, "REJECTED", remarks)
    ticket.status = "REJECTED"
    ticket.team_pmo_deadline = None
    ticket.save()

    notify(ticket.employee.email, f"Ticket #{ticket.id} rejected", f"Remarks: {remarks}")
