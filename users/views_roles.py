import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction, IntegrityError

from Tickets.models import Workflow  # adjust if your import path differs
from users.models import Role        # ✅ Role is in users app

# Workflow must exist in models.py
from Tickets.models import Workflow as TicketWorkflow, WorkflowStep 

# for all list of workflow 
from Tickets.models import Workflow as TicketWorkflow, WorkflowStep

@csrf_exempt
@csrf_exempt
@require_http_methods(["GET"])
def list_roles(request):
    roles = Role.objects.all().values("id", "name", "is_active")
    return JsonResponse(list(roles), safe=False)



@csrf_exempt
@require_http_methods(["POST"])
def add_role(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = (data.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)

    # NOTE: get_or_create can raise IntegrityError in race conditions if unique=True
    try:
        with transaction.atomic():
            role, created = Role.objects.get_or_create(name=name)
    except IntegrityError:
        role = Role.objects.get(name=name)
        created = False

    return JsonResponse({"id": role.id, "name": role.name, "created": created}, status=201 if created else 200)


@csrf_exempt
@require_http_methods(["PATCH"])
def set_role_active(request, role_id):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    is_active = data.get("is_active")
    if not isinstance(is_active, bool):
        return JsonResponse({"error": "is_active must be true/false"}, status=400)

    try:
        role = Role.objects.get(id=role_id)
    except Role.DoesNotExist:
        return JsonResponse({"error": "Role not found"}, status=404)

    role.is_active = is_active
    role.save(update_fields=["is_active"])
    return JsonResponse({"id": role.id, "name": role.name, "is_active": role.is_active})



# ✅ NEW API IN SAME FILE: Create Workflow + Attach Roles
@csrf_exempt
@require_http_methods(["POST"])
def create_workflow_with_roles(request):
    """
    Create workflow + steps dynamically.

    Body:
    {
      "ticket_type": "repair",
      "version": 1,
      "is_active": true,
      "steps": [
        {"role": "TEAM_PMO", "sla_hours": 4},
        {"role": "SENIOR_PMO", "sla_hours": 8},
        {"role": "ADMIN", "sla_hours": 24}
      ]
    }
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    ticket_type = (data.get("ticket_type") or "DEFAULT").strip()
    version = int(data.get("version", 1))
    is_active = bool(data.get("is_active", False))
    steps = data.get("steps") or []

    if not isinstance(steps, list) or len(steps) == 0:
        return JsonResponse({"error": "steps must be a non-empty list"}, status=400)

    # Validate steps quickly
    for i, s in enumerate(steps, start=1):
        if not isinstance(s, dict):
            return JsonResponse({"error": f"Step {i} must be object"}, status=400)
        role_name = (s.get("role") or "").strip()
        if not role_name:
            return JsonResponse({"error": f"Step {i}: role is required"}, status=400)
        if "sla_hours" in s:
            try:
                int(s["sla_hours"])
            except Exception:
                return JsonResponse({"error": f"Step {i}: sla_hours must be int"}, status=400)

    with transaction.atomic():
        wf, created = Workflow.objects.get_or_create(
            ticket_type=ticket_type,
            version=version,
            defaults={"is_active": is_active}
        )

        # Update active flag if needed
        if wf.is_active != is_active:
            wf.is_active = is_active
            wf.save(update_fields=["is_active"])

        # If activating this wf, deactivate others of same ticket_type
        if wf.is_active:
            Workflow.objects.filter(ticket_type=ticket_type).exclude(id=wf.id).update(is_active=False)

        # Replace steps (simple + clean)
        WorkflowStep.objects.filter(workflow=wf).delete()

        out_steps = []
        for idx, s in enumerate(steps, start=1):
            role_name = s["role"].strip()
            sla = int(s.get("sla_hours", 4))

            role_obj, _ = Role.objects.get_or_create(name=role_name)

            st = WorkflowStep.objects.create(
                workflow=wf,
                step_order=idx,
                role=role_obj,
                sla_hours=sla
            )
            out_steps.append({
                "step_order": st.step_order,
                "role": st.role.name,
                "sla_hours": st.sla_hours
            })

    return JsonResponse({
        "workflow_id": wf.id,
        "ticket_type": wf.ticket_type,
        "version": wf.version,
        "is_active": wf.is_active,
        "steps": out_steps
    }, status=201 if created else 200)
# show list of all workflow

@csrf_exempt
@require_http_methods(["GET"])
def list_all_workflows(request):
    """
    Returns all workflows with their attached roles.
    Only the most recent workflow is marked as active.
    """

    workflows = Workflow.objects.all().order_by("-id")

    response_data = []

    # Identify most recent workflow
    latest_workflow_id = workflows[0].id if workflows else None

    for workflow in workflows:
        roles = list(workflow.roles.all().values("id", "name"))

        response_data.append({
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "description": workflow.description,
            "is_active": workflow.id == latest_workflow_id,  # ✅ key logic
            "roles": roles
        })

    return JsonResponse(response_data, safe=False, status=200)
