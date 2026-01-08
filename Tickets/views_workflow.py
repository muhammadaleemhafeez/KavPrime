import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Workflow, WorkflowStep
from users.models import Role

@csrf_exempt
@require_http_methods(["GET"])
def list_workflows(request):
    wfs = Workflow.objects.all().values("id", "ticket_type", "version", "is_active", "created_at")
    return JsonResponse(list(wfs), safe=False)

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

    wf, created = Workflow.objects.get_or_create(
        ticket_type=ticket_type,
        version=version,
        defaults={"is_active": is_active}
    )

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
