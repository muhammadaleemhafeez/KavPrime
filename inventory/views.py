import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Inventory
from django.utils import timezone
from django.db import transaction

from .models import Inventory, AssetDetails
from django.contrib.auth import get_user_model

User = get_user_model()

from users.models import User

# add inventtory

@csrf_exempt
def add_inventory(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    data = json.loads(request.body)

    inventory = Inventory.objects.create(
        item_code=data.get("item_code"),
        item_name=data.get("item_name"),
        category=data.get("category"),
        brand=data.get("brand"),
        model=data.get("model"),
        description=data.get("description"),
        total_quantity=data.get("total_quantity"),
        available_quantity=data.get("total_quantity"),
        minimum_stock_level=data.get("minimum_stock_level"),
        purchase_date=data.get("purchase_date"),
        purchase_price_per_item=data.get("purchase_price_per_item"),
        vendor_name=data.get("vendor_name"),
    )

    return JsonResponse({
        "message": "Inventory added successfully",
        "inventory_id": inventory.id
    })


@csrf_exempt
def update_inventory(request):
    if request.method != "PUT":
        return JsonResponse({"error": "PUT method required"}, status=405)

    data = json.loads(request.body)
    inventory_id = data.get("id")

    try:
        inventory = Inventory.objects.get(id=inventory_id)
    except Inventory.DoesNotExist:
        return JsonResponse({"error": "Inventory not found"}, status=404)

    inventory.item_name = data.get("item_name", inventory.item_name)
    inventory.category = data.get("category", inventory.category)
    inventory.brand = data.get("brand", inventory.brand)
    inventory.model = data.get("model", inventory.model)
    inventory.description = data.get("description", inventory.description)
    inventory.minimum_stock_level = data.get(
        "minimum_stock_level", inventory.minimum_stock_level
    )

    inventory.save()

    return JsonResponse({"message": "Inventory updated successfully"})


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