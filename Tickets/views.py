import json
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Prefetch

from .models import Ticket, AssignedTicket, WorkflowStep
from users.models import User
from Tickets.models import Ticket, Workflow 

from django.contrib.auth.models import User

# ✅ use your services engine (dynamic workflow + fallback)
# from .services import route_new_ticket, approve, reject, add_history


@csrf_exempt
@require_http_methods(["POST"])
def create_ticket(request):
    """
    Employee creates a ticket:
    - Creates Ticket
    - Routes it using the workflow engine based on employee role and workflow steps
    - Sets status dynamically according to the current_role from workflow
    - Dynamically assigns ticket to a user based on workflow target_role and email mapping
    """

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Required fields
    employee_id = data.get("employee_id")
    ticket_type_input = (data.get("ticket_type") or "").strip()
    title = data.get("title")
    description = data.get("description")
    role_override = data.get("role")  # Optional override
    role_email_map = data.get("role_email_map", {})  # Dynamic mapping of role -> email

    if not employee_id or not ticket_type_input or not title or not description:
        return JsonResponse({"error": "employee_id, ticket_type, title, description are required"}, status=400)

    # Map frontend label -> backend key
    ticket_type_map = {
        "Repair an Item": "Repair an Item",
        "Request New Item": "Request New Item",
        "General Issue": "General Issue",
    }

    ticket_type = ticket_type_map.get(ticket_type_input)
    if not ticket_type:
        return JsonResponse({
            "error": "Invalid ticket_type",
            "allowed_ticket_types": list(ticket_type_map.keys())
        }, status=400)

    # Get employee object
    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    # Determine employee role (or use override from request body)
    employee_role_name = role_override or employee.role
    if not employee_role_name:
        return JsonResponse({"error": "Employee has no role assigned"}, status=400)

    # Create ticket without status yet
    ticket = Ticket.objects.create(
        employee=employee,
        ticket_type=ticket_type,
        title=title,
        description=description,
        created_by_role=employee_role_name
    )

    try:
        # -------------------------------
        # ROUTE TICKET BASED ON ACTIVE WORKFLOW
        # -------------------------------
        workflow = Workflow.objects.filter(ticket_type=ticket_type, is_active=True).order_by("-id").first()
        if not workflow:
            raise Exception("No active workflow found for this ticket type")

        ticket.workflow = workflow

        # 1️⃣ Find first workflow step for this employee's role
        first_step = WorkflowStep.objects.filter(
            workflow=workflow,
            role__name=employee_role_name
        ).order_by("step_order").first()

        if not first_step:
            # fallback: first step in workflow
            first_step = WorkflowStep.objects.filter(workflow=workflow).order_by("step_order").first()
            if not first_step:
                raise Exception("Workflow has no steps defined")

        # 2️⃣ Assign ticket workflow fields
        ticket.current_step = first_step.step_order
        ticket.current_role = first_step.target_role.name if first_step.target_role else employee_role_name

        # 3️⃣ Dynamically set status based on current_role
        ticket.status = f"PENDING_{ticket.current_role}" if ticket.current_role else "PENDING"

        # 4️⃣ Assign ticket to a user with the target_role dynamically based on email mapping
        assigned_user = None
        if first_step.target_role:
            target_role_name = first_step.target_role.name
            target_users = User.objects.filter(role=target_role_name)

            # Get the email from the dynamic role_email_map in request
            email_to_assign = role_email_map.get(target_role_name)

            if email_to_assign:
                assigned_user = target_users.filter(email=email_to_assign).first()
            else:
                # fallback: pick first user of that role
                assigned_user = target_users.first()

            ticket.assigned_to = assigned_user

        ticket.save()

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({
        "message": "Ticket created successfully",
        "ticket_id": ticket.id,
        "assigned_to": ticket.assigned_to.id if ticket.assigned_to else None,
        "ticket_type": ticket.ticket_type,
        "status": ticket.status,
        "current_role": ticket.current_role,
        "current_step": ticket.current_step,
        "workflow_id": ticket.workflow_id,
    }, status=201)



@require_http_methods(["GET"])
def list_tickets(request):
    # Read employee_id from query params
    employee_id = request.GET.get("employee_id")

    # If employee_id not provided → return error
    if not employee_id:
        return JsonResponse(
            {"error": "employee_id query parameter is required"},
            status=400
        )

    # Fetch tickets only for that employee_id
    tickets = Ticket.objects.filter(employee_id=employee_id).values(
        "id",
        "employee_id",
        "ticket_type",
        "title",
        "description",
        "status",
        "created_by_role",
        "workflow_id",
        "current_step",
        "current_role",
        "created_at",
        "updated_at",
    )

    # Return result
    return JsonResponse(list(tickets), safe=False)

# get list of all tickets 
@require_http_methods(["GET"])
def list_all_tickets(request):
    """
    Return all tickets without any filtering.
    """
    tickets = Ticket.objects.values(
        "id",
        "employee_id",
        "ticket_type",
        "title",
        "description",
        "status",
        "created_by_role",
        "workflow_id",
        "current_step",
        "current_role",
        "created_at",
        "updated_at",
    )

    return JsonResponse(list(tickets), safe=False, status=200)


@csrf_exempt
@require_http_methods(["PUT"])
def update_ticket_status(request):
    """
    Your existing endpoint:
    Updates all tickets status for employee (kept as is)
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    employee_id = data.get("employee_id")
    new_status = data.get("status")

    if not employee_id or not new_status:
        return JsonResponse({"error": "employee_id and status are required"}, status=400)

    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    tickets = Ticket.objects.filter(employee=employee)
    if not tickets.exists():
        return JsonResponse({"error": "No tickets found for this employee"}, status=404)

    valid_statuses = [choice[0] for choice in Ticket.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return JsonResponse({"error": f"Invalid status. Valid statuses are {valid_statuses}"}, status=400)

    tickets.update(status=new_status)

    return JsonResponse({
        "message": f"Status updated to '{new_status}' for {tickets.count()} ticket(s)"
    }, status=200)


@require_http_methods(["GET"])
def ticket_history(request, ticket_id):
    """
    Returns the full dynamic workflow history for a single ticket.
    - Uses ONLY the workflow path of the creator's main role.
    - Shows states: APPROVED, REJECTED, CURRENT, PENDING
    """

    # -------------------------------
    # 1️⃣ Fetch ticket + workflow
    # -------------------------------
    try:
        t = Ticket.objects.select_related("workflow").get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    creator_role = t.created_by_role

    # -------------------------------
    # 2️⃣ Load creator-role workflow path
    # -------------------------------
    creator_steps = WorkflowStep.objects.filter(
        workflow_id=t.workflow_id,
        role__name=creator_role,
    ).select_related("target_role").order_by("step_order")

    if not creator_steps.exists():
        return JsonResponse({
            "ticket_id": t.id,
            "message": f"No workflow steps found for creator role '{creator_role}'"
        }, status=200)

    # -------------------------------
    # 3️⃣ Load approval/assignment history
    # -------------------------------
    history = AssignedTicket.objects.filter(ticket=t).order_by("action_date")

    # Map: role → last action info
    last_action = {}
    for h in history:
        last_action[h.role] = {
            "status": h.status,
            "remarks": h.remarks,
            "action_date": h.action_date
        }

    steps_out = []

    # -------------------------------
    # 4️⃣ Build step history
    # -------------------------------
    for step in creator_steps:
        target_role = step.target_role.name if step.target_role else None
        
        state = "PENDING"
        remarks = ""
        action_date = None

        # If this role already acted → use that status
        if target_role in last_action:
            act = last_action[target_role]
            state = act["status"]
            remarks = act["remarks"]
            action_date = act["action_date"]

        # Current active reviewer
        if (
            t.current_role == target_role 
            and state == "PENDING"
            and t.status not in ["COMPLETED", "REJECTED"]
        ):
            state = "CURRENT"

        steps_out.append({
            "step_order": step.step_order,
            "role": target_role,
            "sla_hours": step.sla_hours,
            "state": state,
            "remarks": remarks,
            "action_date": action_date,
        })

    # -------------------------------
    # 5️⃣ If rejected → future steps must show PENDING
    # -------------------------------
    if t.status == "REJECTED":
        rejected_step = None
        for s in steps_out:
            if s["state"] == "REJECTED":
                rejected_step = s["step_order"]
                break

        if rejected_step:
            for s in steps_out:
                if s["step_order"] > rejected_step:
                    s["state"] = "PENDING"

    # -------------------------------
    # 6️⃣ Final response for single ticket
    # -------------------------------
    response = {
        "ticket_id": t.id,
        "employee_id": t.employee_id,
        "ticket_type": t.ticket_type,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "workflow_id": t.workflow_id,
        "current_step": t.current_step,
        "current_role": t.current_role,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "steps": steps_out,
    }

    return JsonResponse(response, safe=False, status=200)


# @require_http_methods(["GET"])
# def escalate_ticket(request, ticket_id):
#     """
#     Manual escalation endpoint (kept).
#     For dynamic workflows, we simply log and notify senior (or move status).
#     """
#     try:
#         ticket = Ticket.objects.get(id=ticket_id)
#     except Ticket.DoesNotExist:
#         return JsonResponse({"error": "Ticket not found"}, status=404)

#     # If already completed/rejected, don't escalate
#     if ticket.status in ["COMPLETED", "REJECTED"]:
#         return JsonResponse({"error": f"Ticket is {ticket.status}, cannot escalate."}, status=400)

#     senior = User.objects.filter(role="SENIOR_PMO").first() or User.objects.filter(role_obj__name="SENIOR_PMO").first()
#     if not senior:
#         return JsonResponse({"error": "No SENIOR_PMO user found"}, status=400)

#     # Keep your old behavior
#     ticket.status = "PENDING_SENIOR_PMO"
#     ticket.team_pmo_deadline = None
#     ticket.save(update_fields=["status", "team_pmo_deadline"])

#     add_history(
#         ticket=ticket,
#         assigned_to=senior,
#         role="SENIOR_PMO",
#         status="ESCALATED",
#         remarks="Manually escalated via API"
#     )

#     return JsonResponse({
#         "message": f"Ticket #{ticket.id} escalated to SENIOR_PMO",
#         "ticket_id": ticket.id,
#         "new_status": ticket.status,
#         "assigned_to": senior.id
#     }, status=200)


# ---------------------------
# EMAIL PROCESS ENDPOINTS
# ---------------------------

# @csrf_exempt
# @require_http_methods(["POST"])
# def team_pmo_action(request, ticket_id):
#     """
#     URL: /team-pmo-action/<ticket_id>/
#     Body:
#       { "action": "APPROVE", "remarks": "..." }
#       OR
#       { "action": "REJECT", "remarks": "..." }
#     """
#     try:
#         data = json.loads(request.body.decode("utf-8"))
#     except (json.JSONDecodeError, UnicodeDecodeError):
#         return JsonResponse({"error": "Invalid JSON"}, status=400)

#     action = (data.get("action") or "").upper()
#     remarks = data.get("remarks") or data.get("reason") or ""

#     if action not in ["APPROVE", "REJECT"]:
#         return JsonResponse({"error": "action must be APPROVE or REJECT"}, status=400)

#     # For now actor is the first TEAM_PMO user
#     actor = User.objects.filter(role="TEAM_PMO").first() or User.objects.filter(role_obj__name="TEAM_PMO").first()
#     if not actor:
#         return JsonResponse({"error": "No TEAM_PMO user found"}, status=400)

#     try:
#         ticket = Ticket.objects.get(id=ticket_id)
#     except Ticket.DoesNotExist:
#         return JsonResponse({"error": "Ticket not found"}, status=404)

#     # Optional check: only allow if ticket pending TEAM_PMO
#     if not ticket.status.startswith("PENDING_"):
#         return JsonResponse({"error": f"Ticket is not pending. Current status: {ticket.status}"}, status=400)

#     try:
#         if action == "APPROVE":
#             approve(ticket, actor, remarks=remarks)
#             return JsonResponse({"message": "Ticket approved", "ticket_id": ticket.id, "status": ticket.status})
#         else:
#             reject(ticket, actor, remarks=remarks)
#             return JsonResponse({"message": "Ticket rejected", "ticket_id": ticket.id, "status": ticket.status})
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)


# @csrf_exempt
# @require_http_methods(["POST"])
# def admin_complete(request, ticket_id):
#     """
#     URL: /admin-complete/<ticket_id>/
#     Body: { "remarks": "Item handed over" }

#     This will call approve() using ADMIN actor.
#     In workflow engine:
#       - if ADMIN is last step => COMPLETED
#       - if not last step => moves to next (e.g. FINANCE)
#     """
#     try:
#         data = json.loads(request.body.decode("utf-8"))
#     except (json.JSONDecodeError, UnicodeDecodeError):
#         data = {}

#     remarks = data.get("remarks", "Completed by Admin")

#     actor = User.objects.filter(role="ADMIN").first() or User.objects.filter(role_obj__name="ADMIN").first()
#     if not actor:
#         return JsonResponse({"error": "No ADMIN user found"}, status=400)

#     try:
#         ticket = Ticket.objects.get(id=ticket_id)
#     except Ticket.DoesNotExist:
#         return JsonResponse({"error": "Ticket not found"}, status=404)

#     try:
#         approve(ticket, actor, remarks=remarks)
#         return JsonResponse({
#             "message": "Admin completed/approved step",
#             "ticket_id": ticket.id,
#             "status": ticket.status,
#             "current_step": ticket.current_step,
#             "current_role": ticket.current_role,
#         }, status=200)
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def ticket_action(request, ticket_id):

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    action = (data.get("action") or "").strip().lower()
    remarks = data.get("remarks", "")
    role_email_map = data.get("role_email_map", {})
    ticket_creator_role = (data.get("role") or "").strip()

    if action not in ["approve", "reject"]:
        return JsonResponse({"error": "action must be 'approve' or 'reject'"}, status=400)

    # Fetch ticket
    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    workflow = ticket.workflow
    if not workflow:
        return JsonResponse({"error": "Ticket has no workflow assigned"}, status=400)

    # Use the creator's role to determine workflow path
    creator_role_name = ticket.created_by_role
    current_role_name = ticket.current_role
    current_step_order = ticket.current_step

    if not creator_role_name:
        return JsonResponse({"error": "Ticket has no creator role"}, status=400)

    # Prevent creator from approving their own ticket
    if ticket_creator_role == current_role_name:
        return JsonResponse(
            {"error": f"Role '{ticket_creator_role}' cannot act on their own ticket"},
            status=403
        )

    # -------------------------
    # REJECT LOGIC
    # -------------------------
    if action == "reject":
        ticket.status = "REJECTED"
        ticket.current_role = None
        ticket.current_step = 0  # Set to 0 instead of None (NOT NULL constraint)
        ticket.assigned_to = None
        ticket.save()

        # Log the rejection in history
        AssignedTicket.objects.create(
            ticket=ticket,
            assigned_to=ticket.assigned_to or ticket.employee,
            role=current_role_name,
            status="REJECTED",
            remarks=remarks
        )

        return JsonResponse({
            "message": "Ticket rejected successfully",
            "ticket_id": ticket.id,
            "status": ticket.status
        }, status=200)

    # -------------------------
    # APPROVE LOGIC
    # -------------------------

    # 1️⃣ Get ALL workflow steps for the CREATOR's role (not current_role)
    creator_role_steps = WorkflowStep.objects.filter(
        workflow=workflow,
        role__name=creator_role_name
    ).order_by("step_order")

    if not creator_role_steps.exists():
        return JsonResponse({
            "error": f"No workflow steps found for creator role '{creator_role_name}'"
        }, status=400)

    # 2️⃣ Find the current step in the creator's workflow
    current_step = creator_role_steps.filter(step_order=current_step_order).first()

    if not current_step:
        return JsonResponse({
            "error": f"Current step {current_step_order} not found in workflow for role '{creator_role_name}'"
        }, status=400)

    # Log the approval in history
    AssignedTicket.objects.create(
        ticket=ticket,
        assigned_to=ticket.assigned_to or ticket.employee,
        role=current_role_name,
        status="APPROVED",
        remarks=remarks
    )

    # 3️⃣ Check if there's a next step in the creator's role workflow
    next_step = creator_role_steps.filter(step_order__gt=current_step_order).first()

    if next_step:
        # Move to next step in creator's workflow
        ticket.current_step = next_step.step_order
        next_target_role = next_step.target_role.name if next_step.target_role else None

        if next_target_role:
            ticket.current_role = next_target_role
            ticket.status = f"PENDING_{next_target_role}"

            # Assign to user with next target role
            target_users = User.objects.filter(role=next_target_role)
            assigned_user = (
                target_users.filter(email=role_email_map.get(next_target_role)).first()
                if role_email_map.get(next_target_role)
                else target_users.first()
            )
            ticket.assigned_to = assigned_user
        else:
            # No target role specified, complete ticket
            ticket.current_role = None
            ticket.current_step = 0  # Set to 0 instead of None (NOT NULL constraint)
            ticket.assigned_to = None
            ticket.status = "COMPLETED"

    else:
        # 4️⃣ No more steps in creator's workflow → complete ticket
        ticket.current_role = None
        ticket.current_step = 0  # Set to 0 instead of None (NOT NULL constraint)
        ticket.assigned_to = None
        ticket.status = "COMPLETED"

    ticket.save()

    return JsonResponse({
        "message": "Ticket approved successfully",
        "ticket_id": ticket.id,
        "status": ticket.status,
        "current_role": ticket.current_role,
        "current_step": ticket.current_step,
        "assigned_to": ticket.assigned_to.id if ticket.assigned_to else None
    }, status=200)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_ticket(request, ticket_id):
    """
    Delete a ticket according to dynamic workflow rules:
    - If the first workflow step has NOT been acted on → allow deletion.
    - If the first workflow step has been approved or rejected → deny deletion.
    """
    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    # If ticket has a workflow
    if ticket.workflow_id:
        # Get the first step in workflow
        first_step = WorkflowStep.objects.filter(workflow_id=ticket.workflow_id).order_by("step_order").first()

        if first_step:
            # Check if first step has any action
            first_step_action = AssignedTicket.objects.filter(
                ticket=ticket,
                role=first_step.role.name
            ).order_by("id").first()

            # If first step has action and status is APPROVED or REJECTED → cannot delete
            if first_step_action and first_step_action.status in ["APPROVED", "REJECTED"]:
                return JsonResponse({
                    "error": "Ticket cannot be deleted. First approval step already acted on."
                }, status=403)

    # If no workflow or first step not acted → allow deletion
    ticket.delete()
    return JsonResponse({"message": f"Ticket #{ticket_id} deleted successfully"}, status=200)



# new 

# ---------------------------
# Dashboard API to list tickets assigned to a user
# ---------------------------
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from .models import Ticket

User = get_user_model()

@csrf_exempt
@require_http_methods(["GET"])
def dashboard_tickets(request, user_id):
    """
    Get all tickets assigned to a user according to workflow.
    Works with custom User models.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    tickets = Ticket.objects.filter(assigned_to=user).select_related("workflow", "employee")

    ticket_list = []
    for ticket in tickets:
        # Safely get user display names
        assigned_name = getattr(ticket.assigned_to, "email", str(ticket.assigned_to))
        employee_name = getattr(ticket.employee, "email", str(ticket.employee))

        ticket_list.append({
            "ticket_id": ticket.id,
            "title": ticket.title,
            "description": ticket.description,
            "ticket_type": ticket.ticket_type,
            "status": ticket.status,
            "current_step": ticket.current_step,
            "current_role": ticket.current_role,
            "assigned_to": {
                "id": ticket.assigned_to.id,
                "name": assigned_name,
                "email": getattr(ticket.assigned_to, "email", None)
            } if ticket.assigned_to else None,
            "workflow_id": ticket.workflow.id if ticket.workflow else None,
            "employee": {
                "id": ticket.employee.id,
                "name": employee_name,
                "email": getattr(ticket.employee, "email", None),
                "role": getattr(ticket.employee, "role", None)
            }
        })

    return JsonResponse({
        "message": f"Tickets assigned to {getattr(user, 'email', str(user))}",
        "tickets": ticket_list,
        "total": tickets.count()
    })
