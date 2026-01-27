import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction, IntegrityError

from Tickets.models import Workflow  # adjust if your import path differs
from users.models import Role        # ✅ Role is in users app

# Workflow must exist in models.py
from .models import Role, Workflow  

# for all list of workflow 
from .models import Role, Workflow

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
# ✅ NEW API IN SAME FILE: Create Workflow + Attach Roles
@csrf_exempt
@require_http_methods(["POST"])
def create_workflow_with_roles(request):
    """
    Request JSON accepts:
      - workflow_name (required)
      - description (optional)
      - role_id (optional single)
      - role_name (optional single)
      - role_ids (optional list)
      - role_names (optional list)

    Response:
      - workflow_name
      - description
      - roles: [{id, name, is_active}, ...]
    """

    # Parse JSON
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    workflow_name = (data.get("workflow_name") or "").strip()
    description = (data.get("description") or "").strip()

    if not workflow_name:
        return JsonResponse({"error": "workflow_name is required"}, status=400)

    # role_ids / role_names can be lists
    role_ids = data.get("role_ids") or []
    role_names = data.get("role_names") or []

    # also allow single role_id / role_name
    single_role_id = data.get("role_id", None)
    single_role_name = data.get("role_name", None)

    # Validate list types
    if role_ids and not isinstance(role_ids, list):
        return JsonResponse({"error": "role_ids must be a list"}, status=400)

    if role_names and not isinstance(role_names, list):
        return JsonResponse({"error": "role_names must be a list"}, status=400)

    if not isinstance(role_ids, list):
        role_ids = []
    if not isinstance(role_names, list):
        role_names = []

    # Add single inputs
    if single_role_id is not None:
        role_ids.append(single_role_id)
    if single_role_name is not None:
        role_names.append(single_role_name)

    # Normalize role_ids to int
    clean_role_ids = []
    for rid in role_ids:
        try:
            clean_role_ids.append(int(rid))
        except Exception:
            return JsonResponse({"error": f"Invalid role_id: {rid}"}, status=400)

    # Normalize role_names
    clean_role_names = [str(x).strip() for x in role_names if str(x).strip()]

    try:
        with transaction.atomic():
            # Create workflow (name is unique)
            try:
                workflow = Workflow.objects.create(
                    name=workflow_name,
                    description=description
                )
            except IntegrityError:
                return JsonResponse(
                    {"error": "Workflow with this name already exists"},
                    status=409
                )

            roles_to_attach = []

            # Attach roles by IDs
            if clean_role_ids:
                existing_roles = list(Role.objects.filter(id__in=clean_role_ids))
                found_ids = {r.id for r in existing_roles}
                missing_ids = [rid for rid in clean_role_ids if rid not in found_ids]
                if missing_ids:
                    return JsonResponse(
                        {"error": "Some role_ids not found", "missing_role_ids": missing_ids},
                        status=404
                    )
                roles_to_attach.extend(existing_roles)

            # Create/get roles by Names
            for name in clean_role_names:
                try:
                    role, _created = Role.objects.get_or_create(name=name)
                except IntegrityError:
                    role = Role.objects.get(name=name)
                roles_to_attach.append(role)

            # De-duplicate roles
            unique_roles = list({r.id: r for r in roles_to_attach}.values())

            # Attach to workflow (ManyToMany)
            if unique_roles:
                workflow.roles.add(*unique_roles)

            roles_out = list(workflow.roles.all().values("id", "name", "is_active"))

            return JsonResponse(
                {
                    "workflow_name": workflow.name,
                    "description": workflow.description,
                    "roles": roles_out
                },
                status=201
            )

    except Exception as e:
        return JsonResponse({"error": "Server error", "details": str(e)}, status=500)

# show list of all workflow

@csrf_exempt
@require_http_methods(["GET"])
def list_all_workflows(request):
    """
    Returns all workflows with their attached roles.
    Response:
    [
      {
        "workflow_id": 1,
        "workflow_name": "testing",
        "description": "Workflow for inventory approvals",
        "roles": [{id, name}]
      },
      ...
    ]
    """

    workflows = Workflow.objects.all().order_by("-id")

    response_data = []

    for workflow in workflows:
        roles = list(workflow.roles.all().values("id", "name"))

        response_data.append({
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "description": workflow.description,
            "roles": roles
        })

    return JsonResponse(response_data, safe=False, status=200)
