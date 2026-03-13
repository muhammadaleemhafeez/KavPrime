# Tickets/views.py
import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model

from .models import Ticket, AssignedTicket, WorkflowStep
from Tickets.models import Ticket, Workflow

# ✅ JWT auth
from users.jwt_decorators import jwt_required

from .email_utils import (
    send_ticket_created_email,
    send_ticket_approved_email,
    send_ticket_rejected_email,
    send_ticket_completed_email,
)

logger = logging.getLogger(__name__)
User   = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _apply_priority(ticket, priority, actioner_user):
    """Set priority + audit fields on ticket. Does NOT save — caller must save."""
    if priority and priority in ["CRITICAL", "NON_CRITICAL"]:
        ticket.priority        = priority
        ticket.priority_set_by = actioner_user
        ticket.priority_set_at = timezone.now()


# ─────────────────────────────────────────────────────────────────────────────
# CREATE TICKET
# Priority is NOT accepted here — only approvers can set it
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
@jwt_required
def create_ticket(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    employee          = request.jwt_user  # ✅ Identified from JWT token
    ticket_type_input = (data.get("ticket_type") or "").strip()
    title             = data.get("title")
    description       = data.get("description")
    role_override     = data.get("role")
    role_email_map    = data.get("role_email_map", {})

    if not ticket_type_input or not title or not description:
        return JsonResponse(
            {"error": "ticket_type, title, description are required"},
            status=400
        )

    ticket_type_map = {
        "Repair an Item":   "Repair an Item",
        "Request New Item": "Request New Item",
        "General Issue":    "General Issue",
    }
    ticket_type = ticket_type_map.get(ticket_type_input)
    if not ticket_type:
        return JsonResponse({
            "error": "Invalid ticket_type",
            "allowed_ticket_types": list(ticket_type_map.keys())
        }, status=400)

    employee_role_name = role_override or employee.role
    if not employee_role_name:
        return JsonResponse({"error": "Employee has no role assigned"}, status=400)

    # priority is always None on creation — only approvers can set it
    ticket = Ticket.objects.create(
        employee        = employee,
        ticket_type     = ticket_type,
        title           = title,
        description     = description,
        created_by_role = employee_role_name,
        priority        = None,
    )

    try:
        workflow = Workflow.objects.filter(is_active=True).order_by("-created_at").first()
        if not workflow:
            raise Exception("No active workflow found")

        ticket.workflow = workflow

        first_step = WorkflowStep.objects.filter(
            workflow=workflow, role__name=employee_role_name
        ).order_by("step_order").first()

        if not first_step:
            first_step = WorkflowStep.objects.filter(
                workflow=workflow
            ).order_by("step_order").first()
            if not first_step:
                raise Exception("Workflow has no steps defined")

        ticket.current_step = first_step.step_order
        ticket.current_role = (
            first_step.target_role.name if first_step.target_role else employee_role_name
        )
        ticket.status = f"PENDING_{ticket.current_role}" if ticket.current_role else "PENDING"

        assigned_user = None
        if first_step.target_role:
            target_role_name = first_step.target_role.name
            target_users     = User.objects.filter(role=target_role_name)
            email_to_assign  = role_email_map.get(target_role_name)
            assigned_user = (
                target_users.filter(email=email_to_assign).first()
                if email_to_assign else target_users.first()
            )
            ticket.assigned_to = assigned_user

        ticket.save()

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    if ticket.assigned_to:
        try:
            send_ticket_created_email(ticket, ticket.assigned_to)
        except Exception as e:
            logger.warning(f"[EMAIL] Ticket created email failed — ticket #{ticket.id}: {e}")

    return JsonResponse({
        "message":      "Ticket created successfully",
        "ticket_id":    ticket.id,
        "assigned_to":  ticket.assigned_to.id if ticket.assigned_to else None,
        "ticket_type":  ticket.ticket_type,
        "status":       ticket.status,
        "priority":     ticket.priority,
        "current_role": ticket.current_role,
        "current_step": ticket.current_step,
        "workflow_id":  ticket.workflow_id,
    }, status=201)


# ─────────────────────────────────────────────────────────────────────────────
# SET TICKET PRIORITY  ← STANDALONE ENDPOINT
# Any approver (not the creator) can call this at any time while ticket is open
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["PATCH"])
@jwt_required
def set_ticket_priority(request, ticket_id):
    """
    PATCH /api/tickets/priority/<ticket_id>/
    { "priority": "CRITICAL" }
    Actioner is identified from the Bearer token.
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    priority = (data.get("priority") or "").strip().upper()
    actioner = request.jwt_user  # ✅ Identified from JWT token

    if priority not in ["CRITICAL", "NON_CRITICAL"]:
        return JsonResponse(
            {"error": "priority must be CRITICAL or NON_CRITICAL"},
            status=400
        )

    try:
        ticket = Ticket.objects.select_related(
            "employee", "priority_set_by"
        ).get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    if ticket.status in ["COMPLETED", "REJECTED"]:
        return JsonResponse(
            {"error": f"Cannot set priority on a {ticket.status} ticket"},
            status=400
        )

    # Ticket creator cannot set priority on their own ticket
    if actioner.id == ticket.employee_id:
        return JsonResponse(
            {"error": "Ticket creator cannot set the priority. Only approvers can."},
            status=403
        )

    old_priority           = ticket.priority
    ticket.priority        = priority
    ticket.priority_set_by = actioner
    ticket.priority_set_at = timezone.now()
    ticket.save(update_fields=[
        "priority", "priority_set_by", "priority_set_at", "updated_at"
    ])

    return JsonResponse({
        "message":           f"Ticket #{ticket.id} priority updated to {priority}",
        "ticket_id":         ticket.id,
        "title":             ticket.title,
        "priority":          ticket.priority,
        "previous_priority": old_priority,
        "set_by_id":         actioner.id,
        "set_by_name":       actioner.name,
        "set_by_email":      actioner.email,
        "set_at":            ticket.priority_set_at.isoformat(),
        "ticket_status":     ticket.status,
        "current_role":      ticket.current_role,
    }, status=200)


# ─────────────────────────────────────────────────────────────────────────────
# LIST TICKETS (by employee)
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
@jwt_required
def list_tickets(request):
    # ✅ Employee is identified from JWT token; admins may optionally filter by ?employee_id=
    employee_id = request.GET.get("employee_id") or request.jwt_user.id

    tickets = Ticket.objects.filter(employee_id=employee_id).values(
        "id", "employee_id", "ticket_type", "title", "description",
        "status", "priority",
        "created_by_role", "workflow_id",
        "current_step", "current_role", "created_at", "updated_at",
    )
    return JsonResponse(list(tickets), safe=False)


# ─────────────────────────────────────────────────────────────────────────────
# LIST ALL TICKETS — supports ?priority=CRITICAL filter
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
@jwt_required
def list_all_tickets(request):
    priority_filter = request.GET.get("priority")
    tickets = Ticket.objects.all()

    if priority_filter:
        tickets = tickets.filter(priority__iexact=priority_filter)

    tickets = tickets.values(
        "id", "employee_id", "ticket_type", "title", "description",
        "status", "priority",
        "created_by_role", "workflow_id",
        "current_step", "current_role", "created_at", "updated_at",
    )
    return JsonResponse(list(tickets), safe=False, status=200)


# ─────────────────────────────────────────────────────────────────────────────
# TICKET HISTORY — now includes full priority audit info
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
@jwt_required
def ticket_history(request, ticket_id):
    try:
        t = Ticket.objects.select_related(
            "workflow", "priority_set_by"
        ).get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    creator_role  = t.created_by_role
    creator_steps = WorkflowStep.objects.filter(
        workflow_id=t.workflow_id,
        role__name=creator_role,
    ).select_related("target_role").order_by("step_order")

    if not creator_steps.exists():
        return JsonResponse({
            "ticket_id": t.id,
            "message":   f"No workflow steps found for creator role '{creator_role}'"
        }, status=200)

    history     = AssignedTicket.objects.filter(ticket=t).order_by("action_date")
    last_action = {}
    for h in history:
        last_action[h.role] = {
            "status": h.status, "remarks": h.remarks, "action_date": h.action_date
        }

    steps_out = []
    for step in creator_steps:
        target_role = step.target_role.name if step.target_role else None
        state       = "PENDING"
        remarks     = ""
        action_date = None

        if target_role in last_action:
            act         = last_action[target_role]
            state       = act["status"]
            remarks     = act["remarks"]
            action_date = act["action_date"]

        if (
            t.current_role == target_role
            and state == "PENDING"
            and t.status not in ["COMPLETED", "REJECTED"]
        ):
            state = "CURRENT"

        steps_out.append({
            "step_order": step.step_order, "role": target_role,
            "sla_hours": step.sla_hours,   "state": state,
            "remarks": remarks,             "action_date": action_date,
        })

    if t.status == "REJECTED":
        rejected_step = next(
            (s["step_order"] for s in steps_out if s["state"] == "REJECTED"), None
        )
        if rejected_step:
            for s in steps_out:
                if s["step_order"] > rejected_step:
                    s["state"] = "PENDING"

    return JsonResponse({
        "ticket_id":    t.id,
        "employee_id":  t.employee_id,
        "ticket_type":  t.ticket_type,
        "title":        t.title,
        "description":  t.description,
        "status":       t.status,
        "priority":     t.priority,
        "priority_set_by": {
            "id":    t.priority_set_by.id,
            "name":  t.priority_set_by.name,
            "email": t.priority_set_by.email,
        } if t.priority_set_by else None,
        "priority_set_at": t.priority_set_at.isoformat() if t.priority_set_at else None,
        "workflow_id":  t.workflow_id,
        "current_step": t.current_step,
        "current_role": t.current_role,
        "created_at":   t.created_at,
        "updated_at":   t.updated_at,
        "steps":        steps_out,
    }, safe=False, status=200)


# ─────────────────────────────────────────────────────────────────────────────
# TICKET ACTION — Approve / Reject
# Approver can OPTIONALLY set priority in the same request
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
@jwt_required
def ticket_action(request, ticket_id):

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    action              = (data.get("action") or "").strip().lower()
    remarks             = data.get("remarks", "")
    role_email_map      = data.get("role_email_map", {})
    ticket_creator_role = (data.get("role") or "").strip()
    actioner_user       = request.jwt_user  # ✅ Identified from JWT token
    priority            = (data.get("priority") or "").strip().upper() or None

    if priority and priority not in ["CRITICAL", "NON_CRITICAL"]:
        return JsonResponse(
            {"error": "priority must be CRITICAL or NON_CRITICAL (or omit the field)"},
            status=400
        )

    if action not in ["approve", "reject"]:
        return JsonResponse({"error": "action must be 'approve' or 'reject'"}, status=400)

    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    workflow = ticket.workflow
    if not workflow:
        return JsonResponse({"error": "Ticket has no workflow assigned"}, status=400)

    creator_role_name  = ticket.created_by_role
    current_role_name  = ticket.current_role
    current_step_order = ticket.current_step

    if not creator_role_name:
        return JsonResponse({"error": "Ticket has no creator role"}, status=400)

    if ticket_creator_role == current_role_name:
        return JsonResponse(
            {"error": f"Role '{ticket_creator_role}' cannot act on their own ticket"},
            status=403
        )

    # ✅ actioner_user already set from JWT token above
    # Apply priority if provided alongside the action
    if priority:
        _apply_priority(ticket, priority, actioner_user)

    # ── REJECT ────────────────────────────────────────────────────────────────
    if action == "reject":
        ticket.status       = "REJECTED"
        ticket.current_role = None
        ticket.current_step = 0
        ticket.assigned_to  = None
        ticket.save()

        AssignedTicket.objects.create(
            ticket=ticket, assigned_to=actioner_user,
            role=current_role_name, status="REJECTED", remarks=remarks,
        )

        try:
            send_ticket_rejected_email(ticket, actioner_user, remarks)
        except Exception as e:
            logger.warning(f"[EMAIL] Reject email failed — ticket #{ticket.id}: {e}")

        return JsonResponse({
            "message":   "Ticket rejected successfully",
            "ticket_id": ticket.id,
            "status":    ticket.status,
            "priority":  ticket.priority,
        }, status=200)

    # ── APPROVE ───────────────────────────────────────────────────────────────
    creator_role_steps = WorkflowStep.objects.filter(
        workflow=workflow, role__name=creator_role_name
    ).order_by("step_order")

    if not creator_role_steps.exists():
        return JsonResponse({
            "error": f"No workflow steps found for creator role '{creator_role_name}'"
        }, status=400)

    current_step = creator_role_steps.filter(step_order=current_step_order).first()
    if not current_step:
        return JsonResponse({
            "error": f"Current step {current_step_order} not found in workflow"
        }, status=400)

    AssignedTicket.objects.create(
        ticket=ticket, assigned_to=actioner_user,
        role=current_role_name, status="APPROVED", remarks=remarks,
    )

    next_step = creator_role_steps.filter(step_order__gt=current_step_order).first()

    if next_step:
        ticket.current_step = next_step.step_order
        next_target_role    = next_step.target_role.name if next_step.target_role else None

        if next_target_role:
            ticket.current_role = next_target_role
            ticket.status       = f"PENDING_{next_target_role}"
            target_users        = User.objects.filter(role=next_target_role)
            assigned_user       = (
                target_users.filter(email=role_email_map.get(next_target_role)).first()
                if role_email_map.get(next_target_role) else target_users.first()
            )
            ticket.assigned_to = assigned_user
        else:
            ticket.current_role = None
            ticket.current_step = 0
            ticket.assigned_to  = None
            ticket.status       = "COMPLETED"
    else:
        ticket.current_role = None
        ticket.current_step = 0
        ticket.assigned_to  = None
        ticket.status       = "COMPLETED"

    ticket.save()

    try:
        if ticket.status == "COMPLETED":
            send_ticket_approved_email(ticket, actioner_user, remarks)
            send_ticket_completed_email(ticket)
        else:
            send_ticket_approved_email(ticket, actioner_user, remarks)
            if ticket.assigned_to:
                send_ticket_created_email(ticket, ticket.assigned_to)
    except Exception as e:
        logger.warning(f"[EMAIL] Approve email failed — ticket #{ticket.id}: {e}")

    return JsonResponse({
        "message":      "Ticket approved successfully",
        "ticket_id":    ticket.id,
        "status":       ticket.status,
        "priority":     ticket.priority,
        "current_role": ticket.current_role,
        "current_step": ticket.current_step,
        "assigned_to":  ticket.assigned_to.id if ticket.assigned_to else None,
    }, status=200)


# ─────────────────────────────────────────────────────────────────────────────
# DELETE TICKET
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["DELETE"])
@jwt_required
def delete_ticket(request, ticket_id):
    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    if ticket.workflow_id:
        first_step = WorkflowStep.objects.filter(
            workflow_id=ticket.workflow_id
        ).order_by("step_order").first()

        if first_step:
            first_step_action = AssignedTicket.objects.filter(
                ticket=ticket, role=first_step.role.name
            ).order_by("id").first()

            if first_step_action and first_step_action.status in ["APPROVED", "REJECTED"]:
                return JsonResponse({
                    "error": "Ticket cannot be deleted. First approval step already acted on."
                }, status=403)

    ticket.delete()
    return JsonResponse({"message": f"Ticket #{ticket_id} deleted successfully"}, status=200)


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET"])
@jwt_required
def dashboard_tickets(request, user_id):
    # ✅ JWT authenticates the request; user_id in URL allows admin to view any user's dashboard
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    tickets     = Ticket.objects.filter(assigned_to=user).select_related("workflow", "employee")
    ticket_list = []

    for ticket in tickets:
        ticket_list.append({
            "ticket_id":    ticket.id,
            "title":        ticket.title,
            "description":  ticket.description,
            "ticket_type":  ticket.ticket_type,
            "status":       ticket.status,
            "priority":     ticket.priority,
            "current_step": ticket.current_step,
            "current_role": ticket.current_role,
            "assigned_to": {
                "id":    ticket.assigned_to.id,
                "name":  getattr(ticket.assigned_to, "email", str(ticket.assigned_to)),
                "email": getattr(ticket.assigned_to, "email", None),
            } if ticket.assigned_to else None,
            "workflow_id": ticket.workflow.id if ticket.workflow else None,
            "employee": {
                "id":    ticket.employee.id,
                "name":  getattr(ticket.employee, "email", str(ticket.employee)),
                "email": getattr(ticket.employee, "email", None),
                "role":  getattr(ticket.employee, "role",  None),
            }
        })

    return JsonResponse({
        "message": f"Tickets assigned to {getattr(user, 'email', str(user))}",
        "tickets": ticket_list,
        "total":   tickets.count(),
    })