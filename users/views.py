import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import User

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone


#registration of user
@csrf_exempt
def register_user(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    content_type = request.content_type or ""

    # ✅ Case 1: multipart/form-data (image optional)
    if "multipart/form-data" in content_type:
        data = request.POST
        profile_image = request.FILES.get("profile_image")

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        role = data.get("role", "EMPLOYEE")
        designation = data.get("designation", "")
        employment_status = data.get("employment_status", "ONBOARDING")
        join_date = data.get("join_date") or None

    # ✅ Case 2: application/json (no image in JSON)
    elif "application/json" in content_type:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        profile_image = None  # cannot send file in raw JSON

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        role = data.get("role", "EMPLOYEE")
        designation = data.get("designation", "")
        employment_status = data.get("employment_status", "ONBOARDING")
        join_date = data.get("join_date") or None

    else:
        return JsonResponse({
            "error": "Unsupported Content-Type",
            "detail": "Use application/json or multipart/form-data"
        }, status=415)

    # ✅ Required validation
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)
    if not email:
        return JsonResponse({"error": "email is required"}, status=400)
    if not password:
        return JsonResponse({"error": "password is required"}, status=400)

    # ✅ Duplicate email handling
    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already exists"}, status=409)

    try:
        user = User.objects.create(
            name=name,
            email=email,
            role=role,
            designation=designation,
            profile_image=profile_image,  # ✅ optional, can be None
            employment_status=employment_status,
            join_date=join_date,
        )

        user.set_password(password)
        user.save()

        return JsonResponse({
            "message": "User registered successfully",
            "id": user.id,
            "role": user.role,
            "employment_status": user.employment_status,
            "profile_image": user.profile_image.url if user.profile_image else None
        }, status=201)

    except IntegrityError as e:
        return JsonResponse({"error": "Database error", "detail": str(e)}, status=400)

# add new user

@csrf_exempt
def login_user(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return JsonResponse({"error": "email and password are required"}, status=400)

    try:
        user = User.objects.get(email=email)

        # ✅ Block exited/inactive accounts
        if not user.is_active or user.employment_status == "EXITED":
            return JsonResponse({"error": "Account is inactive / exited"}, status=403)

        # ✅ Correct password verification (works for ALL users)
        if not user.check_password(password):
            return JsonResponse({"error": "Invalid password"}, status=401)

        dashboard_map = {
            "EMPLOYEE": "/employee/dashboard",
            "TEAM_PMO": "/team-pmo/dashboard",
            "SENIOR_PMO": "/senior-pmo/dashboard",
            "ADMIN": "/admin/dashboard",
            "FINANCE": "/finance/dashboard",
            "HR": "/hr/dashboard",
        }

        return JsonResponse({
            "message": "Login successful",
            "user_id": user.id,
            "role": user.role,
            "employment_status": user.employment_status,
            "redirect_url": dashboard_map.get(user.role)
        }, status=200)

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
    user.role = data.get("role", user.role)
    user.designation = data.get("designation", user.designation)
    user.employment_status = data.get("employment_status", user.employment_status)

    # ✅ if password provided, hash it correctly
    if data.get("password"):
        user.set_password(data.get("password"))


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
        "designation": user.designation,
        "designation": user.designation, 
        "employment_status": user.employment_status,
        "join_date": user.join_date.isoformat() if user.join_date else None 
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
    users_list = [{
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": u.role,
        "designation": u.designation,
        "employment_status": u.employment_status,
        "join_date": u.join_date.isoformat() if u.join_date else None,
        "is_active": u.is_active
    } for u in users]

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


@csrf_exempt
def mark_employee_exited(request):
    """
    Admin/HR will call this after returning inventory.
    Disables login + sets EXITED.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    data = json.loads(request.body)
    employee_id = data.get("employee_id")

    if not employee_id:
        return JsonResponse({"error": "employee_id is required"}, status=400)

    try:
        user = User.objects.get(id=employee_id)

        user.employment_status = "EXITED"
        user.is_active = False
        user.exit_date = timezone.now().date()
        user.save(update_fields=["employment_status", "is_active", "exit_date"])

        return JsonResponse({
            "message": "Employee marked as EXITED and login disabled",
            "employee_id": user.id
        }, status=200)

    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)
