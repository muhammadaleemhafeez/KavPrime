import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Max

from .models import Workflow, WorkflowStep
from users.models import Role

#new added

from django.db import transaction

@csrf_exempt
@require_http_methods(["GET"])
def list_workflows(request):
    """
    Returns all workflows + steps (grouped by main role + target_role + SLA).
    ONLY the most recent workflow (globally) is marked ACTIVE.
    """

    # ✅ Find latest workflow globally
    latest_id = (
        Workflow.objects
        .order_by("-id")
        .values_list("id", flat=True)
        .first()
    )

    workflows = Workflow.objects.all().order_by("-id")

    data = []
    for wf in workflows:
        # Get all steps with related roles
        steps_qs = (
            WorkflowStep.objects
            .filter(workflow=wf)
            .select_related("role", "target_role")
            .order_by("step_order")
        )

        # Group steps by main role
        roles_dict = {}
        for s in steps_qs:
            main_role_name = s.role.name
            if main_role_name not in roles_dict:
                roles_dict[main_role_name] = []

            roles_dict[main_role_name].append({
                "step_order": s.step_order,
                "target_role": s.target_role.name if s.target_role else None,
                "sla_hours": s.sla_hours
            })

        # Convert to list
        roles_list = [{"role": r, "steps": steps} for r, steps in roles_dict.items()]

        data.append({
            "workflow_id": wf.id,
            "ticket_type": wf.ticket_type,
            "version": wf.version,
            "is_active": wf.id == latest_id,  # ✅ GLOBAL active
            "workflow_name": wf.workflow_name or "",
            "description": wf.description or "",
            "created_at": wf.created_at,
            "roles": roles_list,
        })

    return JsonResponse(data, safe=False, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def create_workflow(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    ticket_type = (data.get("ticket_type") or "DEFAULT").strip()
    version = int(data.get("version", 1))
    is_active = bool(data.get("is_active", False))

    # ✅ Make this workflow ACTIVE and deactivate others of same ticket_type
    Workflow.objects.filter(ticket_type=ticket_type).exclude(id=wf.id).update(is_active=False)

    if not wf.is_active:
        wf.is_active = True
        wf.save(update_fields=["is_active"])

    # If workflow already existed, you may still want to update is_active
    if not created and is_active and not wf.is_active:
        wf.is_active = True
        wf.save(update_fields=["is_active"])

    # If activating this workflow, deactivate others of same ticket_type
    if wf.is_active:
        Workflow.objects.filter(ticket_type=ticket_type).exclude(id=wf.id).update(is_active=False)

    return JsonResponse({
        "id": wf.id,
        "ticket_type": wf.ticket_type,
        "version": wf.version,
        "is_active": wf.is_active,
        "created": created
    }, status=201 if created else 200)

@csrf_exempt
@require_http_methods(["POST"])
def add_workflow_step(request, workflow_id):
    """
    Body:
    {
      "step_order": 1,
      "role": "TEAM_PMO",
      "sla_hours": 4
    }
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        wf = Workflow.objects.get(id=workflow_id)
    except Workflow.DoesNotExist:
        return JsonResponse({"error": "Workflow not found"}, status=404)

    step_order = int(data.get("step_order"))
    role_name = (data.get("role") or "").strip()
    sla_hours = int(data.get("sla_hours", 4))

    if not role_name:
        return JsonResponse({"error": "role is required"}, status=400)

    role, _ = Role.objects.get_or_create(name=role_name)

    step, created = WorkflowStep.objects.get_or_create(
        workflow=wf,
        step_order=step_order,
        defaults={"role": role, "sla_hours": sla_hours}
    )

    if not created:
        step.role = role
        step.sla_hours = sla_hours
        step.save(update_fields=["role", "sla_hours"])

    return JsonResponse({
        "workflow_id": wf.id,
        "step_id": step.id,
        "step_order": step.step_order,
        "role": step.role.name,
        "sla_hours": step.sla_hours
    }, status=201)

@csrf_exempt
@require_http_methods(["PATCH"])
def activate_workflow(request, workflow_id):
    """
    Activates one workflow and deactivates others in same ticket_type
    """
    try:
        wf = Workflow.objects.get(id=workflow_id)
    except Workflow.DoesNotExist:
        return JsonResponse({"error": "Workflow not found"}, status=404)

    Workflow.objects.filter(ticket_type=wf.ticket_type).update(is_active=False)
    wf.is_active = True
    wf.save(update_fields=["is_active"])
    return JsonResponse({"id": wf.id, "ticket_type": wf.ticket_type, "version": wf.version, "is_active": wf.is_active})


@csrf_exempt
@require_http_methods(["GET"])
def active_workflow_step1_role(request):
    """
    Returns step 1 role of the currently active workflow.
    Response example:
    {
      "workflow_id": 3,
      "ticket_type": "DEFAULT",
      "version": 2,
      "step_id": 7,
      "step_order": 1,
      "role": "TEAM_PMO",
      "sla_hours": 4
    }
    """
    # ✅ get active workflow (latest active if multiple by mistake)
    wf = Workflow.objects.filter(is_active=True).order_by("-id").first()
    if not wf:
        return JsonResponse({"error": "No active workflow found"}, status=404)

    step1 = WorkflowStep.objects.filter(workflow=wf, step_order=1).select_related("role").first()
    if not step1:
        return JsonResponse({"error": "Active workflow has no step 1"}, status=404)

    return JsonResponse({
        "workflow_id": wf.id,
        "ticket_type": wf.ticket_type,
        "version": wf.version,
        "step_id": step1.id,
        "step_order": step1.step_order,
        "role": step1.role.name,
        "sla_hours": step1.sla_hours
    }, status=200)

# ✅ NEW API: Create Workflow + Attach Roles
@csrf_exempt
@require_http_methods(["POST"])
def create_workflow_with_roles(request):
    """
    Create workflow + multiple roles with their own steps, each step can go to a target_role.

    Body example:
    {
      "ticket_type": "DEFAULT",
      "workflow_name": "Multi-role workflow",
      "description": "latest",
      "is_active": true,
      "roles": [
        {
          "role": "TEAM_PMO",
          "steps": [
            { "step_order": 1, "target_role": "SENIOR_PMO", "sla_hours": 4 },
            { "step_order": 2, "target_role": "ADMIN", "sla_hours": 3 }
          ]
        },
        {
          "role": "SENIOR_PMO",
          "steps": [
            { "step_order": 3, "target_role": "ADMIN", "sla_hours": 5 }
          ]
        }
      ]
    }
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    ticket_type = (data.get("ticket_type") or "DEFAULT").strip()
    workflow_name = (data.get("workflow_name") or "").strip()
    description = (data.get("description") or "").strip()
    is_active = bool(data.get("is_active", False))
    roles_data = data.get("roles") or []

    if not roles_data or not isinstance(roles_data, list):
        return JsonResponse({"error": "roles must be a non-empty list"}, status=400)

    # Auto-increment version
    max_version = Workflow.objects.filter(ticket_type=ticket_type).aggregate(Max('version'))['version__max'] or 0
    version = max_version + 1

    # Validate input
    for i, r in enumerate(roles_data, start=1):
        main_role_name = (r.get("role") or "").strip()
        if not main_role_name:
            return JsonResponse({"error": f"Role {i}: role is required"}, status=400)

        steps = r.get("steps")
        if not steps or not isinstance(steps, list):
            return JsonResponse({"error": f"Role {i} ({main_role_name}): steps must be a non-empty list"}, status=400)

        for j, s in enumerate(steps, start=1):
            target_role_name = (s.get("target_role") or "").strip()
            if not target_role_name:
                return JsonResponse({"error": f"Role {i} ({main_role_name}) Step {j}: target_role is required"}, status=400)
            if "sla_hours" in s:
                try:
                    s["sla_hours"] = int(s.get("sla_hours", 4))
                except Exception:
                    return JsonResponse({"error": f"Role {i} ({main_role_name}) Step {j}: sla_hours must be int"}, status=400)

    out_roles = []

    with transaction.atomic():
        # Create workflow
        wf = Workflow.objects.create(
            ticket_type=ticket_type,
            version=version,
            workflow_name=workflow_name,
            description=description,
            is_active=is_active
        )

        # Deactivate other workflows if active
        if wf.is_active:
            Workflow.objects.filter(ticket_type=ticket_type).exclude(id=wf.id).update(is_active=False)

        # Create workflow steps
        for r in roles_data:
            main_role_name = r["role"].strip()
            main_role_obj, _ = Role.objects.get_or_create(name=main_role_name)

            role_steps = []
            role_step_order = 1  # ✅ Start from 1 for each role
            for s in r["steps"]:
                target_role_name = s["target_role"].strip()
                target_role_obj, _ = Role.objects.get_or_create(name=target_role_name)
                sla = s.get("sla_hours", 4)

                step = WorkflowStep.objects.create(
                    workflow=wf,
                    step_order=role_step_order,  # Use per-role step order
                    role=main_role_obj,
                    target_role=target_role_obj,
                    sla_hours=sla
                )
                role_step_order += 1

                role_steps.append({
                    "step_order": step.step_order,
                    "target_role": step.target_role.name,
                    "sla_hours": step.sla_hours
                })

            out_roles.append({
                "role": main_role_obj.name,
                "steps": role_steps
            })

    return JsonResponse({
        "workflow_id": wf.id,
        "ticket_type": wf.ticket_type,
        "version": wf.version,
        "workflow_name": wf.workflow_name,
        "description": wf.description,
        "is_active": wf.is_active,
        "roles": out_roles
    }, status=201)
