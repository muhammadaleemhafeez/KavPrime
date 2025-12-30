import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import User

#registration of user

@csrf_exempt
def register_user(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
 
    data = json.loads(request.body)
 
    user = User.objects.create(
        name=data.get("name"),
        email=data.get("email"),
        password=data.get("password"),
        role=data.get("role", "EMPLOYEE")
    )
 
    return JsonResponse({
        "message": "User registered successfully",
        "id": user.id,
        "role": user.role
    }, status=201)


# add new user

@csrf_exempt
def login_user(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    data = json.loads(request.body)
    email = data.get("email")
    password = data.get("password")

    try:
        user = User.objects.get(email=email)

        if user.password != password:
            return JsonResponse({"error": "Invalid password"}, status=401)

        dashboard_map = {
            "EMPLOYEE": "/employee/dashboard",
            "PMO": "/pmo/dashboard",
            "ADMIN": "/admin/dashboard",
            "FINANCE": "/finance/dashboard",
        }

        return JsonResponse({
            "message": "Login successful",
            "user_id": user.id,
            "role": user.role,
            "redirect_url": dashboard_map[user.role]
        })

    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

#update the user

@csrf_exempt
def update_user(request):
    if request.method != "PUT":
        return JsonResponse({"error": "PUT method required"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    user_id = data.get("id")

    if not user_id:
        return JsonResponse({"error": "User ID is required"}, status=400)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    user.name = data.get("name", user.name)
    user.email = data.get("email", user.email)
    user.password = data.get("password", user.password)
    user.role = data.get("role", user.role)

    user.save()

    return JsonResponse({
        "message": "User updated successfully",
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role
    })


#delete user 
@csrf_exempt
def delete_user(request):
    if request.method != "DELETE":
        return JsonResponse({"error": "DELETE method required"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    user_id = data.get("id")

    if not user_id:
        return JsonResponse({"error": "User ID is required"}, status=400)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    user.delete()

    return JsonResponse({"message": "User deleted successfully"})

@csrf_exempt
def get_all_users(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)

    users = User.objects.all()

    users_list = []
    for user in users:
        users_list.append({
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        })

    return JsonResponse({
        "total_users": len(users_list),
        "users": users_list
    }, status=200)
