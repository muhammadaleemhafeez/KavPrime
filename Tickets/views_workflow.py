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
    Returns all workflows + steps (roles + SLA).
    ONLY the most recent workflow (globally) is marked ACTIVE.
    All others are INACTIVE.
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

        steps_qs = (
            WorkflowStep.objects
            .filter(workflow=wf)
            .select_related("role")
            .order_by("step_order")
        )

        steps = [{
            "step_order": s.step_order,
            "role": s.role.name,
            "sla_hours": s.sla_hours
        } for s in steps_qs]

        data.append({
            "workflow_id": wf.id,
            "ticket_type": wf.ticket_type,
            "version": wf.version,
            "is_active": wf.id == latest_id,  # ✅ GLOBAL active
            "workflow_name": wf.workflow_name or "",
            "description": wf.description or "",
            "created_at": wf.created_at,
            "steps": steps,
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


@csrf_exempt
@require_http_methods(["POST"])
def create_workflow_with_roles(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    ticket_type = (data.get("ticket_type") or "DEFAULT").strip()
    version = int(data.get("version", 1))
    is_active = bool(data.get("is_active", True))

    workflow_name = (data.get("workflow_name") or "").strip()
    description = (data.get("description") or "").strip()

    steps = data.get("steps") or []
    if not isinstance(steps, list) or not steps:
        return JsonResponse({"error": "steps must be a non-empty list"}, status=400)

    # validate steps
    for i, s in enumerate(steps, start=1):
        if not isinstance(s, dict):
            return JsonResponse({"error": f"Step {i} must be object"}, status=400)
        if not (s.get("role") or "").strip():
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
            defaults={
                "is_active": is_active,
                "workflow_name": workflow_name,
                "description": description,
            }
        )

        # ✅ ALWAYS save name/description (even if workflow already existed)
        wf.workflow_name = workflow_name
        wf.description = description
        wf.save(update_fields=["workflow_name", "description"])

        # ✅ GLOBAL latest active
        Workflow.objects.exclude(id=wf.id).update(is_active=False)
        if not wf.is_active:
            wf.is_active = True
            wf.save(update_fields=["is_active"])

        # replace steps
        WorkflowStep.objects.filter(workflow=wf).delete()
        out_steps = []
        for idx, s in enumerate(steps, start=1):
            role_name = (s.get("role") or "").strip()
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

    # ✅ keys ALWAYS included
    return JsonResponse({
        "workflow_id": wf.id,
        "ticket_type": wf.ticket_type,
        "version": wf.version,
        "is_active": wf.is_active,
        "workflow_name": wf.workflow_name or "",
        "description": wf.description or "",
        "steps": out_steps
    }, status=201 if created else 200)


         