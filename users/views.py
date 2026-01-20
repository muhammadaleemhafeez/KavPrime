import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import User

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

#registration of user

@csrf_exempt
def register_user(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    
    data = json.loads(request.body)
    
    # Handle profile image (optional)
    profile_image = None
    if 'profile_image' in request.FILES:
        profile_image = request.FILES['profile_image']
    
    user = User.objects.create(
        name=data.get("name"),
        email=data.get("email"),
        role=data.get("role", "EMPLOYEE"),
        designation=data.get("designation", ""),
        profile_image=profile_image
    )
    user.set_password(data.get("password"))
    user.save()

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
            "TEAM_PMO": "/team-pmo/dashboard",       # ✅ NEW
            "SENIOR_PMO": "/senior-pmo/dashboard",   # ✅ renamed from PMO
            "ADMIN": "/admin/dashboard",
            "FINANCE": "/finance/dashboard",
            "HR": "/hr/dashboard",
        }

        return JsonResponse({
            "message": "Login successful",
            "user_id": user.id,
            "role": user.role,
            "redirect_url": dashboard_map.get(user.role)
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
    user.designation = data.get("designation", user.designation)


    # Handle profile image update
    if 'profile_image' in request.FILES:
        user.profile_image = request.FILES['profile_image']

    user.save()

    return JsonResponse({
        "message": "User updated successfully",
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "designation": user.designation
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



@csrf_exempt
def upload_employee_image(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)
    
    # Get employee ID from the request
    employee_id = request.POST.get("id")
    
    if not employee_id:
        return JsonResponse({"error": "Employee ID is required"}, status=400)

    try:
        # Get the employee from the database
        user = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    # Check if the image file is in the request
    if 'profile_image' not in request.FILES:
        return JsonResponse({"error": "No image file provided"}, status=400)

    # Get the image file
    profile_image = request.FILES['profile_image']
    
    # Save the image to the model
    user.profile_image = profile_image
    user.save()

    return JsonResponse({
        "message": "Image uploaded successfully",
        "user_id": user.id,
        "profile_image_url": user.profile_image.url
    }, status=200)