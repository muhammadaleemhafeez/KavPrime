import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Inventory

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
def issue_inventory(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    data = json.loads(request.body)

    inventory_id = data.get("inventory_id")
    user_id = data.get("user_id")
    quantity = data.get("quantity")

    try:
        inventory = Inventory.objects.get(id=inventory_id)
    except Inventory.DoesNotExist:
        return JsonResponse({"error": "Inventory not found"}, status=404)

    if inventory.available_quantity < quantity:
        return JsonResponse({"error": "Insufficient stock"}, status=400)

    # Auto update quantities
    inventory.available_quantity -= quantity
    inventory.issued_quantity += quantity

    # Update status
    if inventory.available_quantity == 0:
        inventory.status = "OUT_OF_STOCK"
    elif inventory.available_quantity <= inventory.minimum_stock_level:
        inventory.status = "LOW_STOCK"

    inventory.save()

    return JsonResponse({
        "message": "Inventory issued successfully",
        "remaining_stock": inventory.available_quantity
    })

@csrf_exempt
def total_inventory(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)

    inventories = Inventory.objects.all()

    total_items = inventories.count()
    total_quantity = inventories.aggregate(
        total=Sum('total_quantity')
    )['total'] or 0

    data = []
    for item in inventories:
        data.append({
            "id": item.id,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "category": item.category,
            "brand": item.brand,
            "model": item.model,
            "total_quantity": item.total_quantity,
            "minimum_stock_level": item.minimum_stock_level,
        })

    return JsonResponse({
        "total_items": total_items,
        "total_quantity": total_quantity,
        "inventory_list": data
    })