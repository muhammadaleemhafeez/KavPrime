from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from .models import AssignedTicket, Workflow, WorkflowStep

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


# ---------------------------
# Dynamic Role helpers
# ---------------------------
def get_first_by_role(role_name: str):
    # Prefer dynamic role_obj, fallback to old role string
    return (
        User.objects.filter(role_obj__name=role_name, is_active=True).order_by("id").first()
        or User.objects.filter(role=role_name, is_active=True).order_by("id").first()
    )


def get_emails_by_role(role_name: str):
    qs = User.objects.filter(is_active=True).exclude(email__isnull=True).exclude(email="")
    # Prefer dynamic role_obj, fallback to old role string
    emails = list(qs.filter(role_obj__name=role_name).values_list("email", flat=True))
    if emails:
        return emails
    return list(qs.filter(role=role_name).values_list("email", flat=True))


# ---------------------------
# Workflow helpers
# ---------------------------
def get_active_workflow(ticket_type: str):
    wf = Workflow.objects.filter(ticket_type=ticket_type, is_active=True).order_by("-version").first()
    if not wf:
        wf = Workflow.objects.filter(ticket_type="DEFAULT", is_active=True).order_by("-version").first()
    return wf


def get_step(workflow, step_order: int):
    return WorkflowStep.objects.filter(workflow=workflow, step_order=step_order).select_related("role").first()


def start_workflow(ticket):
    """
    Assign step 1 from active workflow.
    """
    wf = get_active_workflow(ticket.ticket_type)
    if not wf:
        return False  # no workflow configured

    step1 = get_step(wf, 1)
    if not step1:
        return False

    role_name = step1.role.name
    assignee = get_first_by_role(role_name)
    if not assignee:
        raise ValueError(f"No user found for role: {role_name}")

    ticket.workflow = wf
    ticket.current_step = 1
    ticket.current_role = role_name
    ticket.step_deadline = timezone.now() + timedelta(hours=step1.sla_hours or SLA_HOURS_FALLBACK)

    # Keep your existing status style for compatibility
    ticket.status = f"PENDING_{role_name}"
    ticket.team_pmo_deadline = None  # stop old SLA if using workflow

    # Your User model has role_name property (recommended). If not, fallback safely:
    creator_role = getattr(ticket.employee, "role_name", None) or getattr(ticket.employee, "role", "")
    ticket.created_by_role = creator_role

    ticket.save(update_fields=[
        "workflow", "current_step", "current_role", "step_deadline",
        "status", "team_pmo_deadline", "created_by_role"
    ])

    add_history(ticket, assignee, role_name, "ASSIGNED", "Auto assigned by workflow engine")
    notify(assignee.email, f"Ticket #{ticket.id} assigned to you", f"Ticket requires your review.\nRole: {role_name}")
    if getattr(ticket.employee, "email", None):
        notify(ticket.employee.email, f"Ticket #{ticket.id} created", f"Your ticket is pending {role_name}.")
    return True


def route_new_ticket(ticket):
    """
    Backward compatible entry point:
    - If workflow exists, use it.
    - Else fallback to your old hardcoded routing.
    """
    if start_workflow(ticket):
        return

    # ---------------------------
    # FALLBACK: your old routing
    # ---------------------------
    creator_role = getattr(ticket.employee, "role_name", None) or ticket.employee.role
    ticket.created_by_role = creator_role

    if creator_role == "EMPLOYEE":
        team = get_first_by_role("TEAM_PMO")
        if not team:
            raise ValueError("No TEAM_PMO user found")

        ticket.status = "PENDING_TEAM_PMO"
        ticket.team_pmo_deadline = timezone.now() + timedelta(hours=SLA_HOURS_FALLBACK)
        ticket.save(update_fields=["status", "team_pmo_deadline", "created_by_role"])

        add_history(ticket, team, "TEAM_PMO", "ASSIGNED", "New ticket assigned to Team PMO")
        notify(team.email, f"Ticket #{ticket.id} assigned to you", "A new ticket requires review.")
        notify(ticket.employee.email, f"Ticket #{ticket.id} created", "Your ticket has been sent to Team PMO.")
        return

    raise ValueError(f"Creator role '{creator_role}' is not allowed to create tickets.")


def approve(ticket, actor, remarks=""):
    """
    Approve using workflow steps if workflow is attached.
    If no workflow -> fallback to old hardcoded.
    """
    actor_role = getattr(actor, "role_name", None) or getattr(actor, "role", "")

    # ✅ WORKFLOW MODE
    if ticket.workflow and ticket.current_step > 0:
        add_history(ticket, actor, actor_role, "APPROVED", remarks)

        next_step_order = ticket.current_step + 1
        next_step = get_step(ticket.workflow, next_step_order)

        # If no next step => completed
        if not next_step:
            ticket.status = "COMPLETED"
            ticket.current_role = None
            ticket.step_deadline = None
            ticket.save(update_fields=["status", "current_role", "step_deadline"])

            # Final emails
            recipients = []
            recipients += get_emails_by_role("TEAM_PMO")
            recipients += get_emails_by_role("HR")
            if getattr(ticket.employee, "email", None):
                recipients.append(ticket.employee.email)

            notify(list(set(recipients)), f"Ticket #{ticket.id} completed", "Ticket process completed.")
            return

        role_name = next_step.role.name
        assignee = get_first_by_role(role_name)
        if not assignee:
            raise ValueError(f"No user found for role: {role_name}")

        ticket.current_step = next_step_order
        ticket.current_role = role_name
        ticket.step_deadline = timezone.now() + timedelta(hours=next_step.sla_hours or SLA_HOURS_FALLBACK)
        ticket.status = f"PENDING_{role_name}"
        ticket.save(update_fields=["current_step", "current_role", "step_deadline", "status"])

        add_history(ticket, assignee, role_name, "ASSIGNED", "Moved to next workflow step")
        notify(assignee.email, f"Ticket #{ticket.id} needs action", f"Ticket moved to you.\nRole: {role_name}")
        return

    # ✅ FALLBACK MODE (tickets without workflow)
    if actor_role == "TEAM_PMO":
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

    if actor_role == "ADMIN":
        # ✅ Admin completes old-flow ticket
        add_history(ticket, actor, "ADMIN", "COMPLETED", remarks)
        ticket.status = "COMPLETED"
        ticket.save(update_fields=["status"])

        # ✅ Final email: TEAM_PMO + HR + employee
        recipients = []
        recipients += get_emails_by_role("TEAM_PMO")
        recipients += get_emails_by_role("HR")
        if getattr(ticket.employee, "email", None):
            recipients.append(ticket.employee.email)

        notify(
            list(set(recipients)),
            f"Ticket #{ticket.id} completed and handed over",
            "Admin processed and handed over the item/service."
        )
        return

    raise ValueError("This role cannot approve tickets.")


def reject(ticket, actor, remarks=""):
    actor_role = getattr(actor, "role_name", None) or getattr(actor, "role", "")
    add_history(ticket, actor, actor_role, "REJECTED", remarks)

    ticket.status = "REJECTED"
    ticket.team_pmo_deadline = None
    ticket.step_deadline = None
    ticket.current_role = None
    ticket.save(update_fields=["status", "team_pmo_deadline", "step_deadline", "current_role"])

    notify(ticket.employee.email, f"Ticket #{ticket.id} rejected", f"Remarks: {remarks}")
