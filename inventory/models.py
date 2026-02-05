from django.db import models
from users.models import User
from django.utils import timezone
from django.db import models


# describe functionality of inventory table
class Inventory(models.Model):

    STATUS_CHOICES = (
        ('AVAILABLE', 'Available'),
        ('LOW_STOCK', 'Low Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
    )

    item_code = models.CharField(max_length=50, unique=True)
    item_name = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    brand = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    total_quantity = models.IntegerField()
    available_quantity = models.IntegerField()
    issued_quantity = models.IntegerField(default=0)
    minimum_stock_level = models.IntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='AVAILABLE'
    )

    purchase_date = models.DateField()
    purchase_price_per_item = models.DecimalField(max_digits=10, decimal_places=2)
    vendor_name = models.CharField(max_length=100)

    # ✅ NEW FIELD
    attachment = models.ImageField(
        upload_to="inventory_attachments/",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.available_quantity} - {self.item_name}"

# describe the asset details
class AssetDetails(models.Model):

    STATUS_CHOICES = (
        ('ISSUED', 'Issued'),
        ('RETURNED', 'Returned'),
        ('DAMAGED', 'Damaged'),
    )

    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE
    )

    user = models.ForeignKey(  # ← Changed from 'User' to 'user'
        User,
        on_delete=models.CASCADE,
        related_name='assets_received'
    )

    quantity_issued = models.PositiveIntegerField()
    quantity_issued_date = models.DateTimeField()

    return_date = models.DateTimeField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ISSUED'
    )

    remarks = models.TextField(blank=True, null=True)

    issued_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assets_issued'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

# purchase request for inventory on low stock
class PurchaseRequest(models.Model):

    REQUEST_TYPES = (
        ("AUTO", "Auto Generated"),
        ("MANUAL", "Manual"),
    )

    STATUS_CHOICES = (
        ("PENDING_FINANCE", "Pending Finance Approval"),
        ("APPROVED_FINANCE", "Finance Approved"),
        ("APPROVED_HR", "HR Approved"),
        ("ORDER_PLACED", "Order Placed"),
        ("COMPLETED", "Completed"),
        ("REJECTED", "Rejected"),
    )

    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    request_type = models.CharField(max_length=10, choices=REQUEST_TYPES)
    triggered_by = models.CharField(max_length=20)  # SYSTEM / ADMIN
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    quantity_needed = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING_FINANCE")
    remarks = models.TextField(blank=True, null=True)

    # ✅ NEW FIELD — Invoice File Upload
    invoice_attachment = models.FileField(upload_to="purchase_invoices/", null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PR-{self.id} | {self.inventory.item_name}"

