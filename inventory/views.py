import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from .models import AssetDetails
from django.views.decorators.http import require_POST
from users.models import User
from django.db.models import F
from .models import PurchaseRequest, Asset , Vendor

# ✅ JWT auth
from users.jwt_decorators import jwt_required

# finance get list of approved request
from django.views.decorators.http import require_GET

import base64 , os , qrcode, logging
from io import BytesIO
# import os
# import qrcode

from django.conf import settings

# image processing
from .models import Asset

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}

MEDIA_QR_PATH = "qr_codes/"  

@require_POST
@csrf_exempt
@jwt_required
def add_inventory(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    attachment = request.FILES.get("attachment")
    warranty_docs = request.FILES.get("warranty_documents")

    if attachment and attachment.content_type not in ALLOWED_IMAGE_TYPES:
        return JsonResponse({"error": "Invalid attachment type."}, status=400)

    def str_to_bool(value):
        return str(value).lower() in ["true", "1", "yes"]

    # Convert quantities safely
    try:
        total_qty = int(data.get("total_quantity", 1))
        minimum_stock = int(data.get("minimum_stock_level", 0))
        available_qty = int(data.get("available_quantity", total_qty))
    except ValueError:
        return JsonResponse({"error": "Quantity fields must be integers."}, status=400)

    try:
        # 1️⃣ Create Asset
        asset = Asset.objects.create(
            asset_tag=data.get("asset_tag"),
            serial_number=data.get("serial_number"),
            model_number=data.get("model_number"),
            brand=data.get("brand"),
            model_name=data.get("model_name"),
            category=data.get("category"),
            type=data.get("type"),
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
            touchscreen=str_to_bool(data.get("touchscreen")),
            curved_screen=str_to_bool(data.get("curved_screen")),
            input_ports=data.get("input_ports"),
            usb_hub_available=str_to_bool(data.get("usb_hub_available")),
            speakers_available=str_to_bool(data.get("speakers_available")),
            connectivity_type=data.get("connectivity_type"),
            purchase_date=data.get("purchase_date"),
            purchase_price=data.get("purchase_price"),
            # vendor_name=data.get("vendor_name"),
            vendor=Vendor.objects.filter(name=data.get("vendor_name")).first() if data.get("vendor_name") else None,
            invoice_number=data.get("invoice_number"),
            warranty_start=data.get("warranty_start"),
            warranty_end=data.get("warranty_end"),
            warranty_status=data.get("warranty_status"),
            condition=data.get("condition") or "NEW",
            current_location=data.get("current_location"),
            remarks=data.get("remarks"),
            attachment=attachment,
            warranty_documents=warranty_docs
        )

        # 2️⃣ Assign to user if provided
        assigned_to_id = data.get("assigned_to")
        if assigned_to_id:
            try:
                user = User.objects.get(id=assigned_to_id)
                asset.assigned_to = user
                asset.save(update_fields=["assigned_to"])
            except User.DoesNotExist:
                return JsonResponse({"error": "Assigned user not found."}, status=400)

        # 3️⃣ Generate static QR code with Inventory API URL
        qr_url = f"http://192.168.18.160:8000/api/inventory/assets/{asset.id}/details/"
        qr = qrcode.make(qr_url)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)

        # Save QR to media/qr_codes/<asset_tag>.png
        qr_folder = os.path.join(settings.MEDIA_ROOT, MEDIA_QR_PATH)
        os.makedirs(qr_folder, exist_ok=True)
        qr_filename = f"{asset.asset_tag}_qr.png"
        qr_path = os.path.join(MEDIA_QR_PATH, qr_filename)
        with open(os.path.join(settings.MEDIA_ROOT, qr_path), "wb") as f:
            f.write(buffer.getvalue())

        # Store QR path in asset
        asset.barcode_qr_code = qr_path[:100]  # max_length safety
        asset.save(update_fields=["barcode_qr_code"])

        # 4️⃣ Return JSON response
        return JsonResponse({
            "message": "Asset added successfully",
            "asset_id": asset.id,
            "asset_tag": asset.asset_tag,
            "assigned_to_id": asset.assigned_to.id if asset.assigned_to else None,
            "qr_code_path": asset.barcode_qr_code,
            "qr_url": qr_url,
            "attachment": asset.attachment.url if asset.attachment else None,
            "warranty_documents": asset.warranty_documents.url if asset.warranty_documents else None
        }, status=201)

    except Exception as e:
        logging.exception("Error adding asset")
        return JsonResponse({"error": "Internal server error."}, status=500)

# -------------------------------
# UPDATE ASSET
# -------------------------------
@csrf_exempt
@jwt_required
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
@jwt_required
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
@jwt_required
def list_inventory(request):
    assets = Asset.objects.all().values()
    return JsonResponse(list(assets), safe=False)


# -------------------------------
# ISSUE ASSET
# -------------------------------
@csrf_exempt
@transaction.atomic
@jwt_required
def issue_inventory(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)

        asset_id        = data.get("asset_id")
        employee_id     = data.get("employee_id")  # Person RECEIVING the asset
        quantity_issued = int(data.get("quantity_issued", 0))
        issued_by       = request.jwt_user           # ✅ Person ISSUING — from JWT token

        issue_date   = data.get("issue_date")
        location     = data.get("location")
        issue_reason = data.get("issue_reason")
        remarks      = data.get("remarks")

        # validation
        if not all([asset_id, employee_id, quantity_issued, issue_date, location, issue_reason]):
            return JsonResponse({
                "error": "asset_id, employee_id, quantity_issued, issue_date, location, issue_reason are required"
            }, status=400)

        if quantity_issued <= 0:
            return JsonResponse({"error": "quantity_issued must be > 0"}, status=400)

        asset    = Asset.objects.select_for_update().get(id=asset_id)
        employee = User.objects.get(id=employee_id)

        if asset.available_quantity < quantity_issued:
            return JsonResponse({"error": "Not enough stock available"}, status=400)

        # Update stock
        # asset.available_quantity -= quantity_issued
        # asset.issued_quantity += quantity_issued

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
            issue_date=issue_date,
            location=location,
            issue_reason=issue_reason,
            remarks=remarks,
            status="ISSUED"
        )

        return JsonResponse({
            "message": "Asset issued successfully",
            "asset_id": asset.id,
            "employee_id": employee.id,
            "issued_by": issued_by.id,
            "quantity_issued": asset_detail.quantity_issued,
            "issue_date": asset_detail.issue_date,
            "location": asset_detail.location,
            "issue_reason": asset_detail.issue_reason,
            "remarks": asset_detail.remarks,
        }, status=201)

    except Asset.DoesNotExist:
        return JsonResponse({"error": "Asset not found"}, status=404)

    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)    

# Add to your existing inventory/views.py

@csrf_exempt
@jwt_required
def list_assets(request):
    """Get all asset details"""
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)
    
    assets = AssetDetails.objects.select_related('asset', 'user', 'issued_by').all()
    
    assets_list = []
    for asset in assets:
        assets_list.append({
            "id":              asset.id,
            "asset_id":        asset.asset.id if asset.asset else None,
            "asset_tag":       asset.asset.asset_tag if asset.asset else "",
            "brand":           asset.asset.brand if asset.asset else "",
            "model_name":      asset.asset.model_name if asset.asset else "",
            "category":        asset.asset.category if asset.asset else "",
            "employee_id":     asset.user.id,
            "employee_name":   asset.user.name,
            "employee_email":  asset.user.email,
            "quantity_issued": asset.quantity_issued,
            "issued_date":     asset.created_at.isoformat(),
            "return_date":     asset.return_date.isoformat() if asset.return_date else None,
            "status":          asset.status,
            "remarks":         asset.remarks or "",
            "issued_by_id":    asset.issued_by.id if asset.issued_by else None,
            "issued_by_name":  asset.issued_by.name if asset.issued_by else "",
            "created_at":      asset.created_at.isoformat(),
            "updated_at":      asset.updated_at.isoformat(),
        })
    
    return JsonResponse({
        "total_assets": len(assets_list),
        "assets": assets_list
    }, safe=False)


# get asset by employee_id

@csrf_exempt
@jwt_required
def get_employee_assets(request, employee_id):
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)

    try:
        employee = User.objects.get(id=employee_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    # 1️⃣ Assets assigned to this employee
    assigned_assets = Asset.objects.filter(assigned_to=employee)

    data = []
    for asset in assigned_assets:
        data.append({
            "asset_id": asset.id,
            "asset_tag": asset.asset_tag,
            "brand": asset.brand,
            "model_name": asset.model_name,
            "category": asset.category,
            "quantity_issued": None,  # Not issued yet
            "status": "ASSIGNED",
            "issued_date": None,
            "return_date": None,
            "issued_by": None,
        })

    # 2️⃣ Assets actually issued (if needed)
    issued_records = AssetDetails.objects.select_related("asset", "issued_by") \
        .filter(user=employee)

    for record in issued_records:
        asset = record.asset
        data.append({
            "asset_id": asset.id,
            "asset_tag": asset.asset_tag,
            "brand": asset.brand,
            "model_name": asset.model_name,
            "category": asset.category,
            "quantity_issued": record.quantity_issued,
            "status": record.status,
            "issued_date": record.created_at.isoformat(),
            "return_date": record.return_date.isoformat() if record.return_date else None,
            "issued_by": record.issued_by.name if record.issued_by else None,
        })

    return JsonResponse({
        "employee_id": employee.id,
        "employee_name": employee.name,
        "total_assets": len(data),
        "assets": data
    })


@csrf_exempt
@jwt_required
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
@jwt_required
def get_asset_detail(request, asset_id):
    """Get single asset detail by ID"""
    if request.method != "GET":
        return JsonResponse({"error": "GET method required"}, status=405)
    
    try:
        asset = AssetDetails.objects.select_related('asset', 'user', 'issued_by').get(id=asset_id)
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
@jwt_required
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
@jwt_required
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
@jwt_required
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
            asset_id           = data.get("asset_id")
            quantity_needed    = data.get("quantity_needed")
            remarks            = data.get("remarks", "")
            request_type       = data.get("request_type", "MANUAL")
            triggered_by       = data.get("triggered_by", "ADMIN")
            invoice_attachment = None
        else:
            asset_id           = request.POST.get("asset_id")
            quantity_needed    = request.POST.get("quantity_needed")
            remarks            = request.POST.get("remarks", "")
            request_type       = request.POST.get("request_type", "MANUAL")
            triggered_by       = request.POST.get("triggered_by", "ADMIN")
            invoice_attachment = request.FILES.get("invoice_attachment")

        created_by = request.jwt_user  # ✅ Identified from JWT token

        if not asset_id or not quantity_needed:
            return JsonResponse({"error": "asset_id and quantity_needed are required"}, status=400)

        asset = Asset.objects.get(id=asset_id)

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
@jwt_required
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
@jwt_required
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
@jwt_required
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
@jwt_required
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


# add vendor details
@csrf_exempt
@jwt_required
def add_vendor(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)

    try:
        data = json.loads(request.body)
        
        vendor = Vendor.objects.create(
            name=data.get("name"),
            address=data.get("address"),
            contact_person=data.get("contact_person"),
            phone=data.get("phone"),
            email=data.get("email"),
            gst_number=data.get("gst_number"),
        )

        return JsonResponse({
            "message": "Vendor added successfully",
            "vendor_id": vendor.id,
        }, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
    

# get vendor list
@csrf_exempt
@jwt_required
def list_vendors(request):
    if request.method != "GET":
        return JsonResponse({"error": "Only GET method allowed"}, status=405)

    vendors = Vendor.objects.all()

    vendor_list = []
    for v in vendors:
        vendor_list.append({
            "id": v.id,
            "name": v.name,
            "address": v.address,
            "contact_person": v.contact_person,
            "phone": v.phone,
            "email": v.email,
            "gst_number": v.gst_number
        })

    return JsonResponse({"vendors": vendor_list}, status=200)



@csrf_exempt
@jwt_required
def edit_vendor(request, vendor_id):
    if request.method != "PUT":
        return JsonResponse({"error": "Only PUT method allowed"}, status=405)

    try:
        vendor = Vendor.objects.get(id=vendor_id)
    except Vendor.DoesNotExist:
        return JsonResponse({"error": "Vendor not found"}, status=404)

    try:
        data = json.loads(request.body)

        # Only update fields that are provided in request
        if "name" in data:
            vendor.name = data["name"]
        if "address" in data:
            vendor.address = data["address"]
        if "contact_person" in data:
            vendor.contact_person = data["contact_person"]
        if "phone" in data:
            vendor.phone = data["phone"]
        if "email" in data:
            vendor.email = data["email"]
        if "gst_number" in data:
            vendor.gst_number = data["gst_number"]

        vendor.save()

        return JsonResponse({
            "message":        "Vendor updated successfully",
            "vendor_id":      vendor.id,
            "name":           vendor.name,
            "address":        vendor.address,
            "contact_person": vendor.contact_person,
            "phone":          vendor.phone,
            "email":          vendor.email,
            "gst_number":     vendor.gst_number,
        }, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@jwt_required
def delete_vendor(request, vendor_id):
    if request.method != "DELETE":
        return JsonResponse({"error": "Only DELETE method allowed"}, status=405)

    try:
        vendor = Vendor.objects.get(id=vendor_id)
    except Vendor.DoesNotExist:
        return JsonResponse({"error": "Vendor not found"}, status=404)

    # Check if vendor has assets linked to it
    linked_assets = Asset.objects.filter(vendor=vendor).count()
    if linked_assets > 0:
        return JsonResponse({
            "error": f"Cannot delete vendor. {linked_assets} asset(s) are linked to this vendor."
        }, status=400)

    vendor_name = vendor.name
    vendor.delete()

    return JsonResponse({
        "message":   f"Vendor '{vendor_name}' deleted successfully",
        "vendor_id": vendor_id,
    }, status=200)

from django.shortcuts import get_object_or_404, render

def asset_details(request, asset_id):
    asset = get_object_or_404(Asset, id=asset_id)
    return render(request, "asset_detail.html", {"asset": asset})