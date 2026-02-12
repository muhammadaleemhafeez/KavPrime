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
    return Workflow.objects.filter(ticket_type=ticket_type, is_active=True).order_by("-id").first()


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
    
    # creator_role = getattr(ticket.employee, "role_name", None) or getattr(ticket.employee, "role", "")
    # ticket.created_by_role = creator_role

    

    ticket.save(update_fields=[
        "workflow", "current_step", "current_role", "step_deadline",
        "status", "team_pmo_deadline", "created_by_role"
    ])

    add_history(ticket, assignee, role_name, "ASSIGNED", "Auto assigned by workflow engine")
    notify(assignee.email, f"Ticket #{ticket.id} assigned to you", f"Ticket requires your review.\nRole: {role_name}")
    if getattr(ticket.employee, "email", None):
        notify(ticket.employee.email, f"Ticket #{ticket.id} created", f"Your ticket is pending {role_name}.")
    return True

# def route_new_ticket(ticket: Ticket):
#     """
#     Route a new ticket to the first step of the active workflow.
#     Fully dynamic — no hardcoded roles.
#     """
#     workflow = Workflow.objects.filter(
#         ticket_type=ticket.ticket_type,
#         is_active=True
#     ).order_by("-id").first()

#     if not workflow:
#         # fallback if no workflow
#         ticket.workflow = None
#         ticket.current_role = "TEAM_PMO"
#         ticket.current_step = 1
#         ticket.status = "PENDING_TEAM_PMO"
#         ticket.assigned_to = get_first_by_role("TEAM_PMO")
#         ticket.step_deadline = None
#         ticket.save()
#         add_history(ticket, ticket.assigned_to, "TEAM_PMO", "ASSIGNED", "Fallback assignment")
#         return

#     # Get first step in workflow
#     step1 = WorkflowStep.objects.filter(workflow=workflow).order_by("role", "step_order").first()
#     if not step1:
#         # fallback if misconfigured
#         ticket.workflow = workflow
#         ticket.current_role = "TEAM_PMO"
#         ticket.current_step = 1
#         ticket.status = "PENDING_TEAM_PMO"
#         ticket.assigned_to = get_first_by_role("TEAM_PMO")
#         ticket.step_deadline = None
#         ticket.save()
#         add_history(ticket, ticket.assigned_to, "TEAM_PMO", "ASSIGNED", "Fallback assignment")
#         return

#     # Determine assignee (target_role preferred)
#     next_role_name = step1.target_role.name if step1.target_role else step1.role.name
#     assignee = get_first_by_role(next_role_name)

#     ticket.workflow = workflow
#     ticket.current_role = next_role_name
#     ticket.current_step = step1.step_order
#     ticket.status = f"PENDING_{next_role_name}"
#     ticket.assigned_to = assignee
#     ticket.step_deadline = timezone.now() + timedelta(hours=step1.sla_hours)
#     ticket.save()
#     add_history(ticket, assignee, next_role_name, "ASSIGNED", f"Workflow step 1 assigned ({next_role_name})")



# def approve(ticket, actor, remarks=""):
#     """
#     Approve a ticket following workflow steps dynamically.
#     Fully dynamic — no hardcoded next role.
#     """
#     actor_role_name = getattr(actor, "role_name", None) or getattr(actor, "role", "")
#     add_history(ticket, actor, actor_role_name, "APPROVED", remarks)

#     if not ticket.workflow:
#         # fallback mode
#         ticket.status = "COMPLETED"
#         ticket.current_role = None
#         ticket.current_step = None
#         ticket.assigned_to = None
#         ticket.save()
#         return

#     workflow = ticket.workflow
#     current_role_name = ticket.current_role
#     current_step_order = ticket.current_step

#     # Steps in current role
#     role_steps = WorkflowStep.objects.filter(workflow=workflow, role__name=current_role_name).order_by("step_order")

#     # Next step in same role
#     next_step = role_steps.filter(step_order__gt=current_step_order).first()

#     if next_step:
#         ticket.current_step = next_step.step_order
#         ticket.current_role = next_step.target_role.name if next_step.target_role else next_step.role.name
#     else:
#         last_step = role_steps.last()
#         if last_step and last_step.target_role:
#             next_role = last_step.target_role
#             next_role_steps = WorkflowStep.objects.filter(workflow=workflow, role=next_role).order_by("step_order")
#             ticket.current_role = next_role.name
#             ticket.current_step = next_role_steps.first().step_order if next_role_steps else 1
#         else:
#             ticket.current_role = None
#             ticket.current_step = None
#             ticket.status = "COMPLETED"

#     # Assign ticket
#     if ticket.current_role:
#         ticket.assigned_to = get_first_by_role(ticket.current_role)
#         ticket.status = f"PENDING_{ticket.current_role}"
#     else:
#         ticket.assigned_to = None
#         ticket.status = "COMPLETED"

#     ticket.save()

#     if ticket.assigned_to:
#         add_history(ticket, ticket.assigned_to, ticket.current_role, "ASSIGNED", "Moved to next workflow step")
#         notify(
#             ticket.assigned_to.email,
#             f"Ticket #{ticket.id} requires your action",
#             f"Your role: {ticket.current_role}"
#         )




# def reject(ticket, actor, remarks=""):
#     """
#     Reject a ticket and clear workflow assignment.
#     """
#     actor_role_name = getattr(actor, "role_name", None) or getattr(actor, "role", "")
#     add_history(ticket, actor, actor_role_name, "REJECTED", remarks)

#     ticket.status = "REJECTED"
#     ticket.current_role = None
#     ticket.current_step = None
#     ticket.assigned_to = None
#     ticket.step_deadline = None
#     ticket.save()

#     if getattr(ticket.employee, "email", None):
#         notify(
#             ticket.employee.email,
#             f"Ticket #{ticket.id} rejected",
#             f"Remarks: {remarks}"
#         )



def get_active_workflow_global():
    # ✅ GLOBAL: pick latest active workflow
    return Workflow.objects.filter(is_active=True).order_by("-id").first()