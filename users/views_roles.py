import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Role

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

    role, created = Role.objects.get_or_create(name=name)
    return JsonResponse({"id": role.id, "name": role.name, "created": created}, status=201)

@csrf_exempt
@require_http_methods(["PATCH"])
def set_role_active(request, role_id):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    is_active = data.get("is_active")
    if is_active not in [True, False]:
        return JsonResponse({"error": "is_active must be true/false"}, status=400)

    try:
        role = Role.objects.get(id=role_id)
    except Role.DoesNotExist:
        return JsonResponse({"error": "Role not found"}, status=404)

    role.is_active = is_active
    role.save(update_fields=["is_active"])
    return JsonResponse({"id": role.id, "name": role.name, "is_active": role.is_active})
