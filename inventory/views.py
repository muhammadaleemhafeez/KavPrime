import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from .models import AssetDetails
from django.views.decorators.http import require_POST
from users.models import User
from django.db.models import F
from .models import PurchaseRequest, Asset

# finance get list of approved request 
from django.views.decorators.http import require_GET



# image processing
from .models import Asset

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}  # jpeg covers jpg + jpeg

# add inventtory

@csrf_exempt
@require_POST
def add_inventory(request):
    """
    Add a new asset to the inventory.
    """
    # Parse JSON body
    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    attachment = request.FILES.get("attachment")
    warranty_docs = request.FILES.get("warranty_documents")

    # Validate uploaded file type
    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}  # jpeg covers jpg + jpeg
    if attachment and attachment.content_type not in ALLOWED_IMAGE_TYPES:
        return JsonResponse(
            {"error": "Only jpg, jpeg, and png files are allowed for attachment."},
            status=400
        )

    # Convert quantities to integers
    try:
        total_qty = int(data.get("total_quantity", 1))
        minimum_stock = int(data.get("minimum_stock_level", 0))
        available_qty = int(data.get("available_quantity", total_qty))
    except ValueError:
        return JsonResponse(
            {"error": "total_quantity, available_quantity, and minimum_stock_level must be integers."},
            status=400
        )

    try:
        asset = Asset.objects.create(
            asset_tag=data.get("asset_tag"),  # NOW this will be correctly read
            serial_number=data.get("serial_number"),
            model_number=data.get("model_number"),
            brand=data.get("brand"),
            model_name=data.get("model_name"),
            category=data.get("category"),
            type=data.get("type"),
            barcode_qr_code=data.get("barcode_qr_code"),

            total_quantity=total_qty,
            available_quantity=available_qty,
            minimum_stock_level=minimum_stock,

            processor=data.get("processor"),
            processor_generation=data.get("processor_generation"),
            ram_size=data.get("ram_size"),
            ram_type=data.get("ram_type"),
            storage_type=data.get("storage_type"),
            storage_capacity=data.get("storage_capacity"),
            graphics_card=data.get("graphics_card"),
            battery_health=data.get("battery_health"),
            os_installed=data.get("os_installed"),

            screen_size_inch=data.get("screen_size_inch") or None,
            resolution=data.get("resolution"),
            panel_type=data.get("panel_type"),
            touchscreen=data.get("touchscreen") in ["true", "True", "1"],
            curved_screen=data.get("curved_screen") in ["true", "True", "1"],
            input_ports=data.get("input_ports"),
            usb_hub_available=data.get("usb_hub_available") in ["true", "True", "1"],
            speakers_available=data.get("speakers_available") in ["true", "True", "1"],

            connectivity_type=data.get("connectivity_type"),

            purchase_date=data.get("purchase_date"),
            purchase_price=data.get("purchase_price"),
            vendor_name=data.get("vendor_name"),
            invoice_number=data.get("invoice_number"),
            warranty_start=data.get("warranty_start"),
            warranty_end=data.get("warranty_end"),
            warranty_status=data.get("warranty_status"),

            status=data.get("status") or "AVAILABLE",
            condition=data.get("condition") or "NEW",
            current_location=data.get("current_location"),
            assigned_to_id=data.get("assigned_to") or None,
            assigned_date=data.get("assigned_date"),
            returned_date=data.get("returned_date"),

            remarks=data.get("remarks"),
            attachment=attachment,
            warranty_documents=warranty_docs
        )

        return JsonResponse({
            "message": "Asset added successfully",
            "asset_id": asset.id,
            "asset_tag": asset.asset_tag,
            "attachment": asset.attachment.url if asset.attachment else None,
            "warranty_documents": asset.warranty_documents.url if asset.warranty_documents else None
        }, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# -------------------------------
# UPDATE ASSET
# -------------------------------
@csrf_exempt
def update_inventory(request):
    if request.method != "PUT":
        return JsonResponse({"error": "PUT method required"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    asset_id = data.get("id")
    if not asset_id:
        return JsonResponse({"error": "Asset ID is required"}, status=400)

    try:
        asset = Asset.objects.get(id=asset_id)
    except Asset.DoesNotExist:
        return JsonResponse({"error": "Asset not found"}, status=404)

    # Validate new total quantity
    new_total_quantity = data.get("total_quantity", asset.total_quantity)
    if new_total_quantity < asset.issued_quantity:
        return JsonResponse({
            "error": f"Total quantity ({new_total_quantity}) cannot be less than issued quantity ({asset.issued_quantity})"
        }, status=400)
    if new_total_quantity < 0:
        return JsonResponse({"error": "Total quantity cannot be negative"}, status=400)

    # Update fields
    asset.asset_tag = data.get("asset_tag", asset.asset_tag)
    asset.brand = data.get("brand", asset.brand)
    asset.model_name = data.get("model_name", asset.model_name)
    asset.category = data.get("category", asset.category)
    asset.type = data.get("type", asset.type)
    asset.barcode_qr_code = data.get("barcode_qr_code", asset.barcode_qr_code)
    asset.total_quantity = new_total_quantity
    asset.available_quantity = new_total_quantity - asset.issued_quantity
    asset.minimum_stock_level = data.get("minimum_stock_level", asset.minimum_stock_level)

    # Auto update status
    if asset.available_quantity == 0:
        asset.status = "OUT_OF_STOCK"
    elif asset.available_quantity <= asset.minimum_stock_level:
        asset.status = "LOW_STOCK"
    else:
        asset.status = "AVAILABLE"

    # Optional updates
    asset.purchase_date = data.get("purchase_date", asset.purchase_date)
    asset.purchase_price = data.get("purchase_price", asset.purchase_price)
    asset.vendor_name = data.get("vendor_name", asset.vendor_name)
    asset.invoice_number = data.get("invoice_number", asset.invoice_number)
    asset.save()

    return JsonResponse({
        "message": "Asset updated successfully",
        "asset_id": asset.id,
        "total_quantity": asset.total_quantity,
        "available_quantity": asset.available_quantity,
        "issued_quantity": asset.issued_quantity,
        "status": asset.status
    })


# -------------------------------
# DELETE ASSET
# -------------------------------
@csrf_exempt
def delete_inventory(request):
    if request.method != "DELETE":
        return JsonResponse({"error": "DELETE method required"}, status=405)

    data = json.loads(request.body)
    asset_id = data.get("id")
    if not asset_id:
        return JsonResponse({"error": "Asset ID required"}, status=400)

    try:
        asset = Asset.objects.get(id=asset_id)
        asset.delete()
        return JsonResponse({"message": "Asset deleted successfully"})
    except Asset.DoesNotExist:
        return JsonResponse({"error": "Asset not found"}, status=404)


# -------------------------------
# LIST ALL ASSETS
# -------------------------------
@csrf_exempt
def list_inventory(request):
    assets = Asset.objects.all().values()
    return JsonResponse(list(assets), safe=False)


# -------------------------------
# ISSUE ASSET
# -------------------------------
@csrf_exempt
@transaction.atomic
def issue_inventory(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)
        asset_id = data.get("asset_id")
        employee_id = data.get("employee_id")
        issued_by_id = data.get("issued_by_id")
        quantity_issued = int(data.get("quantity_issued", 0))

        if not all([asset_id, employee_id, issued_by_id, quantity_issued]):
            return JsonResponse({"error": "asset_id, employee_id, issued_by_id, quantity_issued are required"}, status=400)
        if quantity_issued <= 0:
            return JsonResponse({"error": "quantity_issued must be > 0"}, status=400)

        asset = Asset.objects.select_for_update().get(id=asset_id)
        employee = User.objects.get(id=employee_id)
        issued_by = User.objects.get(id=issued_by_id)

        if asset.available_quantity < quantity_issued:
            return JsonResponse({"error": "Not enough stock available"}, status=400)

        # Update stock
        asset.available_quantity -= quantity_issued
        asset.issued_quantity += quantity_issued
        if asset.available_quantity == 0:
            asset.status = "OUT_OF_STOCK"
        elif asset.available_quantity <= asset.minimum_stock_level:
            asset.status = "LOW_STOCK"
        else:
            asset.status = "AVAILABLE"
        asset.save()

        # Create issue record
        asset_detail = AssetDetails.objects.create(
            asset=asset,
            user=employee,
            quantity_issued=quantity_issued,
            issued_by=issued_by,
            status="ISSUED"
        )

        return JsonResponse({
            "message": "Asset issued successfully",
            "asset_detail_id": asset_detail.id,
            "remaining_quantity": asset.available_quantity
        }, status=201)

    except Asset.DoesNotExist:
        return JsonResponse({"error": "Asset not found"}, status=404)
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


# -------------------------------
# RETURN SINGLE ASSET
# -------------------------------
@csrf_exempt
@transaction.atomic
def return_asset(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)
        asset_detail_id = data.get("asset_id")
        status = data.get("status", "RETURNED")
        remarks = data.get("remarks", "")

        if status not in ["RETURNED", "DAMAGED"]:
            return JsonResponse({"error": "status must be RETURNED or DAMAGED"}, status=400)

        asset_detail = AssetDetails.objects.select_for_update().select_related("asset").get(id=asset_detail_id)
        asset = asset_detail.asset

        if asset_detail.status in ["RETURNED", "DAMAGED"]:
            return JsonResponse({"message": "Asset already closed", "asset_id": asset_detail.id}, status=200)

        # Update asset detail
        asset_detail.status = status
        asset_detail.return_date = timezone.now()
        if remarks:
            asset_detail.remarks = remarks
        asset_detail.save(update_fields=["status", "return_date", "remarks", "updated_at"])

        # Update stock only if RETURNED
        if status == "RETURNED":
            asset.available_quantity += asset_detail.quantity_issued
            asset.issued_quantity -= asset_detail.quantity_issued
            if asset.available_quantity == 0:
                asset.status = "OUT_OF_STOCK"
            elif asset.available_quantity <= asset.minimum_stock_level:
                asset.status = "LOW_STOCK"
            else:
                asset.status = "AVAILABLE"
            asset.save(update_fields=["available_quantity", "issued_quantity", "status", "updated_at"])

        return JsonResponse({
            "message": f"Asset marked as {status}",
            "asset_id": asset_detail.id,
            "asset_total_quantity": asset.total_quantity,
            "asset_available_quantity": asset.available_quantity
        }, status=200)

    except AssetDetails.DoesNotExist:
        return JsonResponse({"error": "Asset detail not found"}, status=404)
    except Asset.DoesNotExist:
        return JsonResponse({"error": "Asset not found"}, status=404)
    

# return all asset when employee leaving company 


# -------------------------------
# RETURN ALL ASSETS FOR EMPLOYEE
# -------------------------------
@csrf_exempt
@transaction.atomic
def return_all_employee_assets(request, employee_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    assets = AssetDetails.objects.select_for_update().filter(user=employee, status="ISSUED")
    if not assets.exists():
        return JsonResponse({"message": "No assets to return for this employee"}, status=200)

    returned_ids = []
    for ad in assets:
        asset = ad.asset
        ad.status = "RETURNED"
        ad.return_date = timezone.now()
        ad.save(update_fields=["status", "return_date", "updated_at"])

        asset.available_quantity += ad.quantity_issued
        asset.issued_quantity -= ad.quantity_issued
        if asset.available_quantity == 0:
            asset.status = "OUT_OF_STOCK"
        elif asset.available_quantity <= asset.minimum_stock_level:
            asset.status = "LOW_STOCK"
        else:
            asset.status = "AVAILABLE"
        asset.save(update_fields=["available_quantity", "issued_quantity", "status", "updated_at"])
        returned_ids.append(ad.id)

    return JsonResponse({
        "message": f"All assets returned for employee {employee.name}",
        "employee_id": employee.id,
        "returned_asset_ids": returned_ids
    }, status=200)


# -------------------------------
# CREATE PURCHASE REQUEST
# -------------------------------
@csrf_exempt
def create_purchase_request(request):
    """
    Create a Purchase Request (Manual or Auto)
    Can include invoice_attachment.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        # JSON or form-data
        if request.content_type == "application/json":
            data = json.loads(request.body)
            asset_id = data.get("asset_id")
            quantity_needed = data.get("quantity_needed")
            remarks = data.get("remarks", "")
            request_type = data.get("request_type", "MANUAL")
            triggered_by = data.get("triggered_by", "ADMIN")
            created_by_id = data.get("created_by")
            invoice_attachment = None
        else:
            asset_id = request.POST.get("asset_id")
            quantity_needed = request.POST.get("quantity_needed")
            remarks = request.POST.get("remarks", "")
            request_type = request.POST.get("request_type", "MANUAL")
            triggered_by = request.POST.get("triggered_by", "ADMIN")
            created_by_id = request.POST.get("created_by")
            invoice_attachment = request.FILES.get("invoice_attachment")

        if not asset_id or not quantity_needed:
            return JsonResponse({"error": "asset_id and quantity_needed are required"}, status=400)

        asset = Asset.objects.get(id=asset_id)
        created_by = User.objects.get(id=created_by_id) if created_by_id else None

        pr = PurchaseRequest.objects.create(
            asset=asset,
            request_type=request_type,
            triggered_by=triggered_by,
            created_by=created_by,
            quantity_needed=quantity_needed,
            remarks=remarks,
            invoice_attachment=invoice_attachment,
            status="PENDING_FINANCE"
        )

        return JsonResponse({
            "message": "Purchase request created",
            "request_id": pr.id,
            "status": pr.status,
            "invoice_attachment": pr.invoice_attachment.url if pr.invoice_attachment else None
        }, status=201)

    except Asset.DoesNotExist:
        return JsonResponse({"error": "Asset not found"}, status=404)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# finance reaction on  inventory purchase request 
# -------------------------------
# FINANCE APPROVE REQUEST
# -------------------------------
@csrf_exempt
def finance_approve_request(request, request_id):
    try:
        pr = PurchaseRequest.objects.get(id=request_id)

        if pr.status != "PENDING_FINANCE":
            return JsonResponse({"error": "Request is not pending finance approval"}, status=400)

        pr.status = "APPROVED_FINANCE"
        pr.save(update_fields=["status"])

        return JsonResponse({
            "message": "Finance approved successfully",
            "request_id": pr.id,
            "next_step": "HR approval required"
        })

    except PurchaseRequest.DoesNotExist:
        return JsonResponse({"error": "Purchase request not found"}, status=404)


# when finance Approved then final Approval by HR
@csrf_exempt
def hr_approve_request(request, request_id):
    try:
        pr = PurchaseRequest.objects.get(id=request_id)

        if pr.status != "APPROVED_FINANCE":
            return JsonResponse({"error": "Finance approval pending"}, status=400)

        pr.status = "APPROVED_HR"
        pr.save(update_fields=["status"])

        return JsonResponse({
            "message": "HR approved successfully",
            "request_id": pr.id,
            "next_step": "Order can be placed now"
        })

    except PurchaseRequest.DoesNotExist:
        return JsonResponse({"error": "Purchase request not found"}, status=404)
    

# finance purchase  inventory add data 

# -------------------------------
# FINANCE MARK AS PURCHASED
# -------------------------------
@csrf_exempt
def finance_mark_as_purchased(request, request_id):
    """
    Finance final step: mark request as purchased, upload invoice, and update asset quantity.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        pr = PurchaseRequest.objects.get(id=request_id)

        if pr.status != "APPROVED_HR":
            return JsonResponse({"error": "HR approval pending or invalid status"}, status=400)

        # Multipart/form-data required for file upload
        invoice_file = request.FILES.get("invoice_attachment")
        purchased_quantity = request.POST.get("purchased_quantity")

        if not purchased_quantity:
            return JsonResponse({"error": "purchased_quantity is required"}, status=400)

        purchased_quantity = int(purchased_quantity)
        if purchased_quantity <= 0:
            return JsonResponse({"error": "purchased_quantity must be greater than 0"}, status=400)

        if invoice_file:
            pr.invoice_attachment = invoice_file

        # Update Asset quantity
        asset = pr.asset
        asset.total_quantity += purchased_quantity
        asset.available_quantity += purchased_quantity
        if asset.available_quantity == 0:
            asset.status = "OUT_OF_STOCK"
        elif asset.available_quantity <= asset.minimum_stock_level:
            asset.status = "LOW_STOCK"
        else:
            asset.status = "AVAILABLE"
        asset.save(update_fields=["total_quantity", "available_quantity", "status"])

        # Update request
        pr.status = "ORDER_PLACED"
        pr.save(update_fields=["status", "invoice_attachment"])

        return JsonResponse({
            "message": f"Purchase completed for request {pr.id}",
            "request_id": pr.id,
            "asset_id": asset.id,
            "asset_total_quantity": asset.total_quantity,
            "asset_available_quantity": asset.available_quantity,
            "status": pr.status,
            "invoice_attachment": pr.invoice_attachment.url if pr.invoice_attachment else None
        })

    except PurchaseRequest.DoesNotExist:
        return JsonResponse({"error": "Purchase request not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# -------------------------------
# LIST PURCHASE REQUESTS
# -------------------------------
@csrf_exempt
@require_GET
def list_purchase_requests(request):
    status = request.GET.get("status")

    if status:
        prs = PurchaseRequest.objects.filter(status=status)
    else:
        prs = PurchaseRequest.objects.all()

    prs_list = []
    for pr in prs:
        prs_list.append({
            "id": pr.id,
            "asset_id": pr.asset.id,
            "asset_name": pr.asset.model_name,
            "request_type": pr.request_type,
            "triggered_by": pr.triggered_by,
            "created_by": pr.created_by.name if pr.created_by else None,
            "quantity_needed": pr.quantity_needed,
            "status": pr.status,
            "remarks": pr.remarks,
            "invoice_attachment": pr.invoice_attachment.url if pr.invoice_attachment else None,
            "created_at": pr.created_at.isoformat(),
            "updated_at": pr.updated_at.isoformat(),
        })

    return JsonResponse({
        "total_requests": len(prs_list),
        "purchase_requests": prs_list
    }, safe=False)