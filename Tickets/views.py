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

# ✅ use your services engine (dynamic workflow + fallback)
from .services import route_new_ticket, approve, reject, add_history


@csrf_exempt
@require_http_methods(["POST"])
def create_ticket(request):
    """
    Employee creates a ticket:
    - Creates Ticket
    - Routes it using the workflow engine based on employee role and workflow steps
    - Sets status dynamically according to the current_role from workflow
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

        # 4️⃣ Assign ticket to a user with the target_role (if any)
        if first_step.target_role:
            assigned_user = User.objects.filter(role=first_step.target_role.name).first()
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
def ticket_history(request, employee_id=None, ticket_id=None):
    """
    Fetch ticket workflow history:
    - Filter by employee_id OR ticket_id
    - For each ticket, show workflow steps with status: APPROVED / REJECTED / CURRENT / PENDING
    URL examples:
      /api/tickets/ticket-history/employee/<employee_id>/
      /api/tickets/ticket-history/ticket/<ticket_id>/
    """

    # Filter tickets based on ticket_id or employee_id
    if ticket_id:
        tickets = Ticket.objects.filter(id=ticket_id).select_related("workflow")
    elif employee_id:
        tickets = Ticket.objects.filter(employee_id=employee_id).select_related("workflow").order_by("-id")
    else:
        return JsonResponse({"error": "employee_id or ticket_id is required"}, status=400)

    if not tickets.exists():
        return JsonResponse({"message": "No tickets found"}, status=200)

    response = []

    for t in tickets:
        # Get workflow steps if workflow exists
        if t.workflow_id:
            steps_qs = (
                WorkflowStep.objects
                .filter(workflow_id=t.workflow_id)
                .select_related("role")
                .order_by("step_order")
            )
            workflow_steps = [{
                "step_order": s.step_order,
                "role": s.role.name,
                "sla_hours": s.sla_hours
            } for s in steps_qs]
        else:
            workflow_steps = []

        # Get history for ticket actions
        hist = (
            AssignedTicket.objects
            .filter(ticket_id=t.id)
            .order_by("action_date")
            .values("role", "status", "remarks", "action_date", "assigned_to_id")
        )

        last_action_by_role = {}
        for h in hist:
            last_action_by_role[h["role"]] = h

        steps_out = []

        for step in workflow_steps:
            role = step["role"]

            step_state = "PENDING"
            action_date = None
            remarks = ""

            if role in last_action_by_role:
                st = last_action_by_role[role]["status"]

                if st == "APPROVED":
                    step_state = "APPROVED"
                elif st == "REJECTED":
                    step_state = "REJECTED"
                else:
                    step_state = "CURRENT"

                action_date = last_action_by_role[role]["action_date"]
                remarks = last_action_by_role[role]["remarks"] or ""

            # Mark as CURRENT if it's the current_role and still pending
            if t.current_role == role and step_state == "PENDING":
                step_state = "CURRENT"

            steps_out.append({
                "step_order": step["step_order"],
                "role": role,
                "sla_hours": step["sla_hours"],
                "state": step_state,
                "action_date": action_date,
                "remarks": remarks,
            })

        # If ticket rejected, mark remaining steps as PENDING
        if t.status == "REJECTED" and workflow_steps:
            rejected_step_order = None
            for s in steps_out:
                if s["state"] == "REJECTED":
                    rejected_step_order = s["step_order"]
                    break
            if rejected_step_order:
                for s in steps_out:
                    if s["step_order"] > rejected_step_order:
                        s["state"] = "PENDING"

        response.append({
            "ticket_id": t.id,
            "employee_id": t.employee_id,
            "ticket_type": t.ticket_type,
            "title": t.title,
            "description": t.description,   # ✅ Added description
            "status": t.status,
            "workflow_id": t.workflow_id,
            "current_step": t.current_step,
            "current_role": t.current_role,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
            "steps": steps_out
        })

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
    """
    Generic ticket action API for dynamic workflow approval/rejection
    Handles multi-role workflow and dynamically updates ticket status
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    action = (data.get("action") or "").upper()
    remarks = data.get("remarks", "")

    if action not in ["APPROVE", "REJECT"]:
        return JsonResponse({"error": "action must be APPROVE or REJECT"}, status=400)

    try:
        ticket = Ticket.objects.get(id=ticket_id)
    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)

    workflow = ticket.workflow
    if not workflow:
        return JsonResponse({"error": "Ticket has no workflow assigned"}, status=400)

    # Determine actor (current role user)
    actor_role_name = ticket.current_role
    actor = User.objects.filter(role=actor_role_name).first()
    if not actor:
        return JsonResponse({"error": f"No user found for role {actor_role_name}"}, status=400)

    try:
        # -------------------------------
        # Handle APPROVE / REJECT actions
        # -------------------------------
        if action == "REJECT":
            # Mark ticket as rejected
            ticket.status = "REJECTED"
            ticket.save()
        else:
            # APPROVE: move to next workflow step
            current_step_order = ticket.current_step

            # Find next step in workflow after current step
            next_step = WorkflowStep.objects.filter(
                workflow=workflow,
                step_order__gt=current_step_order
            ).order_by("step_order").first()

            if next_step:
                # Move ticket to next step
                ticket.current_step = next_step.step_order
                ticket.current_role = next_step.target_role.name if next_step.target_role else next_step.role.name

                # Dynamically set status based on current_role
                ticket.status = f"PENDING_{ticket.current_role}" if ticket.current_role else "PENDING"

                # Assign ticket to a user in the next role
                assigned_user = User.objects.filter(role=ticket.current_role).first()
                ticket.assigned_to = assigned_user
            else:
                # No next step: mark ticket as completed
                ticket.status = "COMPLETED"
                ticket.current_role = None
                ticket.current_step = ticket.current_step  # remains last step
                ticket.assigned_to = None

            ticket.save()

        # Optionally: log action in AssignedTicket table
        AssignedTicket.objects.create(
            ticket=ticket,
            assigned_to=actor,
            role=actor_role_name,
            status=action,
            remarks=remarks
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({
        "message": f"Ticket {action}D successfully",
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
