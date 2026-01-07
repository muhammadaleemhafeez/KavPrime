import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Inventory
from django.utils import timezone
from django.db import transaction
from .models import Inventory, AssetDetails
from django.views.decorators.http import require_POST
from users.models import User

# image processing
from .models import Inventory

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}  # jpeg covers jpg + jpeg

# add inventtory

@csrf_exempt
@require_POST
def add_inventory(request):
    # form-data fields
    data = request.POST

    # uploaded file
    attachment = request.FILES.get("attachment")

    # validate image type
    if attachment and attachment.content_type not in ALLOWED_IMAGE_TYPES:
        return JsonResponse(
            {"error": "Only jpg, jpeg, and png files are allowed."},
            status=400
        )

    # Convert numeric fields safely
    try:
        total_qty = int(data.get("total_quantity", 0))
        minimum_stock = int(data.get("minimum_stock_level", 0))
    except ValueError:
        return JsonResponse(
            {"error": "total_quantity and minimum_stock_level must be integers."},
            status=400
        )

    inventory = Inventory.objects.create(
        item_code=data.get("item_code"),
        item_name=data.get("item_name"),
        category=data.get("category"),
        brand=data.get("brand"),
        model=data.get("model"),
        description=data.get("description"),
        total_quantity=total_qty,
        available_quantity=total_qty,
        minimum_stock_level=minimum_stock,
        purchase_date=data.get("purchase_date"),
        purchase_price_per_item=data.get("purchase_price_per_item"),
        vendor_name=data.get("vendor_name"),
        attachment=attachment,   # ✅ saves file
    )

    return JsonResponse({
        "message": "Inventory added successfully",
        "inventory_id": inventory.id,
        "attachment": inventory.attachment.url if inventory.attachment else None
    }, status=201)


@csrf_exempt
def update_inventory(request):
    if request.method != "PUT":
        return JsonResponse({"error": "PUT method required"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    inventory_id = data.get("id")

    # Validate inventory_id is provided
    if not inventory_id:
        return JsonResponse({"error": "Inventory ID is required"}, status=400)

    try:
        inventory = Inventory.objects.get(id=inventory_id)
    except Inventory.DoesNotExist:
        return JsonResponse({"error": "Inventory not found"}, status=404)

    # Get the new total_quantity if being updated
    new_total_quantity = data.get("total_quantity", inventory.total_quantity)
    
    # 🔹 CRITICAL VALIDATION: Total quantity cannot be less than issued quantity
    if new_total_quantity < inventory.issued_quantity:
        return JsonResponse({
            "error": f"Total quantity ({new_total_quantity}) cannot be less than already issued quantity ({inventory.issued_quantity})"
        }, status=400)
    
    # 🔹 Validate total_quantity is not negative
    if new_total_quantity < 0:
        return JsonResponse({
            "error": "Total quantity cannot be negative"
        }, status=400)

    # Update basic fields
    inventory.item_name = data.get("item_name", inventory.item_name)
    inventory.category = data.get("category", inventory.category)
    inventory.brand = data.get("brand", inventory.brand)
    inventory.model = data.get("model", inventory.model)
    inventory.description = data.get("description", inventory.description)
    inventory.minimum_stock_level = data.get("minimum_stock_level", inventory.minimum_stock_level)
    inventory.purchase_date = data.get("purchase_date", inventory.purchase_date)
    inventory.purchase_price_per_item = data.get("purchase_price_per_item", inventory.purchase_price_per_item)
    inventory.vendor_name = data.get("vendor_name", inventory.vendor_name)
    
    # Update total_quantity
    inventory.total_quantity = new_total_quantity
    
    # 🔹 AUTO-CALCULATE available_quantity (don't allow manual override)
    # Available = Total - Issued
    inventory.available_quantity = inventory.total_quantity - inventory.issued_quantity
    
    # 🔹 Update status based on available quantity
    if inventory.available_quantity == 0:
        inventory.status = "OUT_OF_STOCK"
    elif inventory.available_quantity <= inventory.minimum_stock_level:
        inventory.status = "LOW_STOCK"
    else:
        inventory.status = "AVAILABLE"

    inventory.save()

    return JsonResponse({
        "message": "Inventory updated successfully",
        "inventory_id": inventory.id,
        "total_quantity": inventory.total_quantity,
        "available_quantity": inventory.available_quantity,
        "issued_quantity": inventory.issued_quantity,
        "status": inventory.status
    })

@csrf_exempt
def delete_inventory(request):
    if request.method != "DELETE":
        return JsonResponse({"error": "DELETE method required"}, status=405)

    data = json.loads(request.body)
    inventory_id = data.get("id")

    try:
        inventory = Inventory.objects.get(id=inventory_id)
    except Inventory.DoesNotExist:
        return JsonResponse({"error": "Inventory not found"}, status=404)

    inventory.delete()
    return JsonResponse({"message": "Inventory deleted successfully"})

#list of inventory

@csrf_exempt
def list_inventory(request):
    inventories = Inventory.objects.all().values()
    return JsonResponse(list(inventories), safe=False)


@csrf_exempt
@transaction.atomic
def issue_inventory(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)

        inventory_id = data.get("inventory_id")
        employee_id = data.get("employee_id")
        issued_by_id = data.get("issued_by_id")
        quantity_issued = data.get("quantity_issued")

        # 🔹 Basic validation
        if not all([inventory_id, employee_id, issued_by_id, quantity_issued]):
            return JsonResponse(
                {"error": "inventory_id, employee_id, issued_by_id, quantity_issued are required"},
                status=400
            )

        quantity_issued = int(quantity_issued)
        if quantity_issued <= 0:
            return JsonResponse({"error": "quantity_issued must be greater than 0"}, status=400)

        # 🔹 Fetch objects (locked row)
        inventory = Inventory.objects.select_for_update().get(id=inventory_id)
        employee = User.objects.get(id=employee_id)
        issued_by = User.objects.get(id=issued_by_id)

        # 🔹 Check availability
        if inventory.available_quantity < quantity_issued:
            return JsonResponse(
                {"error": "Not enough inventory available"},
                status=400
            )

        # 🔹 Update inventory quantities
        inventory.available_quantity -= quantity_issued
        inventory.issued_quantity += quantity_issued

        # 🔹 Update inventory status
        if inventory.available_quantity == 0:
            inventory.status = "OUT_OF_STOCK"
        elif inventory.available_quantity <= inventory.minimum_stock_level:
            inventory.status = "LOW_STOCK"
        else:
            inventory.status = "AVAILABLE"

        inventory.save()

        # 🔹 Create asset record
        asset = AssetDetails.objects.create(
            inventory=inventory,
            user=employee,
            quantity_issued=quantity_issued,
            quantity_issued_date=timezone.now(),
            issued_by=issued_by,
            status="ISSUED"
        )

        return JsonResponse({
            "message": "Inventory issued successfully",
            "asset_id": asset.id,
            "remaining_quantity": inventory.available_quantity
        }, status=201)

    except Inventory.DoesNotExist:
        return JsonResponse({"error": "Inventory not found"}, status=404)

    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# Add to your existing inventory/views.py

@csrf_exempt
def list_assets(request):
    """Get all asset details"""
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)
    
    assets = AssetDetails.objects.select_related('inventory', 'user', 'issued_by').all()
    
    assets_list = []
    for asset in assets:
        assets_list.append({
            "id": asset.id,
            "inventory_id": asset.inventory.id,
            "inventory_name": asset.inventory.item_name,
            "inventory_code": asset.inventory.item_code,
            "brand": asset.inventory.brand,
            "model": asset.inventory.model,
            "employee_id": asset.user.id,
            "employee_name": asset.user.name,
            "employee_email": asset.user.email,
            "quantity_issued": asset.quantity_issued,
            "quantity_issued_date": asset.quantity_issued_date.isoformat(),
            "return_date": asset.return_date.isoformat() if asset.return_date else None,
            "status": asset.status,
            "remarks": asset.remarks,
            "issued_by_id": asset.issued_by.id,
            "issued_by_name": asset.issued_by.name,
            "created_at": asset.created_at.isoformat(),
            "updated_at": asset.updated_at.isoformat(),
        })
    
    return JsonResponse({
        "total_assets": len(assets_list),
        "assets": assets_list
    }, safe=False)


@csrf_exempt
def get_employee_assets(request, employee_id):
    """Get all assets issued to a specific employee"""
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)
    
    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)
    
    assets = AssetDetails.objects.select_related('inventory', 'issued_by').filter(user=employee)
    
    assets_list = []
    for asset in assets:
        assets_list.append({
            "id": asset.id,
            "inventory_id": asset.inventory.id,
            "inventory_name": asset.inventory.item_name,
            "inventory_code": asset.inventory.item_code,
            "brand": asset.inventory.brand,
            "model": asset.inventory.model,
            "quantity_issued": asset.quantity_issued,
            "quantity_issued_date": asset.quantity_issued_date.isoformat(),
            "return_date": asset.return_date.isoformat() if asset.return_date else None,
            "status": asset.status,
            "remarks": asset.remarks,
            "issued_by_id": asset.issued_by.id,
            "issued_by_name": asset.issued_by.name,
            "created_at": asset.created_at.isoformat(),
            "updated_at": asset.updated_at.isoformat(),
        })
    
    return JsonResponse({
        "employee_id": employee.id,
        "employee_name": employee.name,
        "employee_email": employee.email,
        "total_assets": len(assets_list),
        "assets": assets_list
    }, safe=False)


@csrf_exempt
def get_inventory_assets(request, inventory_id):
    """Get all assets for a specific inventory item"""
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)
    
    try:
        inventory = Inventory.objects.get(id=inventory_id)
    except Inventory.DoesNotExist:
        return JsonResponse({"error": "Inventory not found"}, status=404)
    
    assets = AssetDetails.objects.select_related('user', 'issued_by').filter(inventory=inventory)
    
    assets_list = []
    for asset in assets:
        assets_list.append({
            "id": asset.id,
            "employee_id": asset.user.id,
            "employee_name": asset.user.name,
            "employee_email": asset.user.email,
            "quantity_issued": asset.quantity_issued,
            "quantity_issued_date": asset.quantity_issued_date.isoformat(),
            "return_date": asset.return_date.isoformat() if asset.return_date else None,
            "status": asset.status,
            "remarks": asset.remarks,
            "issued_by_id": asset.issued_by.id,
            "issued_by_name": asset.issued_by.name,
            "created_at": asset.created_at.isoformat(),
            "updated_at": asset.updated_at.isoformat(),
        })
    
    return JsonResponse({
        "inventory_id": inventory.id,
        "inventory_name": inventory.item_name,
        "inventory_code": inventory.item_code,
        "total_issued": inventory.issued_quantity,
        "total_assets": len(assets_list),
        "assets": assets_list
    }, safe=False)


@csrf_exempt
def get_asset_detail(request, asset_id):
    """Get single asset detail by ID"""
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)
    
    try:
        asset = AssetDetails.objects.select_related('inventory', 'user', 'issued_by').get(id=asset_id)
    except AssetDetails.DoesNotExist:
        return JsonResponse({"error": "Asset not found"}, status=404)
    
    return JsonResponse({
        "id": asset.id,
        "inventory": {
            "id": asset.inventory.id,
            "name": asset.inventory.item_name,
            "code": asset.inventory.item_code,
            "brand": asset.inventory.brand,
            "model": asset.inventory.model,
            "category": asset.inventory.category,
        },
        "employee": {
            "id": asset.user.id,
            "name": asset.user.name,
            "email": asset.user.email,
            "role": asset.user.role,
        },
        "quantity_issued": asset.quantity_issued,
        "quantity_issued_date": asset.quantity_issued_date.isoformat(),
        "return_date": asset.return_date.isoformat() if asset.return_date else None,
        "status": asset.status,
        "remarks": asset.remarks,
        "issued_by": {
            "id": asset.issued_by.id,
            "name": asset.issued_by.name,
            "email": asset.issued_by.email,
        },
        "created_at": asset.created_at.isoformat(),
        "updated_at": asset.updated_at.isoformat(),
    })