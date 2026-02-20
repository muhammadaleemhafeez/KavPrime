from django.db import models
from users.models import User
from django.utils import timezone
from django.db import models


# describe functionality of inventory table
class Asset(models.Model):

    # ==============================
    # COMMON CHOICES
    # ==============================

    STATUS_CHOICES = (
        ('AVAILABLE', 'Available'),
        ('ISSUED', 'Issued'),
        ('DAMAGED', 'Damaged'),
        ('LOST', 'Lost'),
        ('SCRAPPED', 'Scrapped'),
        ('LOW_STOCK', 'Low Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
    )

    CONDITION_CHOICES = (
        ('NEW', 'New'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('POOR', 'Poor'),
    )

    WARRANTY_STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
    )

    CATEGORY_CHOICES = (
        ('LAPTOP', 'Laptop'),
        ('DESKTOP', 'Desktop'),
        ('MOUSE', 'Mouse'),
        ('KEYBOARD', 'Keyboard'),
        ('MONITOR', 'Monitor'),
        ('PRINTER', 'Printer'),
        ('OTHER', 'Other'),
    )

    CONNECTIVITY_CHOICES = (
        ('USB', 'USB Wired'),
        ('BLUETOOTH', 'Bluetooth'),
        ('WIRELESS', 'Wireless'),
    )

    PANEL_TYPE_CHOICES = (
        ('IPS', 'IPS'),
        ('TN', 'TN'),
        ('VA', 'VA'),
        ('OLED', 'OLED'),
    )

    # ==============================
    # ASSET IDENTIFICATION
    # ==============================

    asset_tag = models.CharField(max_length=100, unique=True)
    serial_number = models.CharField(max_length=100, null=True, blank=True)
    model_number = models.CharField(max_length=100, null=True, blank=True)
    brand = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    type = models.CharField(max_length=100, null=True, blank=True)
    barcode_qr_code = models.CharField(max_length=150, null=True, blank=True)

    # ==============================
    # INVENTORY QUANTITY TRACKING
    # ==============================

    total_quantity = models.IntegerField(default=1)
    available_quantity = models.IntegerField(default=1)
    issued_quantity = models.IntegerField(default=0)
    minimum_stock_level = models.IntegerField(default=0)

    # ==============================
    # HARDWARE SPECIFICATIONS (Laptop/Desktop)
    # ==============================

    processor = models.CharField(max_length=100, null=True, blank=True)
    processor_generation = models.CharField(max_length=50, null=True, blank=True)
    ram_size = models.CharField(max_length=50, null=True, blank=True)
    ram_type = models.CharField(max_length=50, null=True, blank=True)
    storage_type = models.CharField(max_length=50, null=True, blank=True)
    storage_capacity = models.CharField(max_length=50, null=True, blank=True)
    graphics_card = models.CharField(max_length=100, null=True, blank=True)
    battery_health = models.IntegerField(null=True, blank=True)
    os_installed = models.CharField(max_length=100, null=True, blank=True)

    # ==============================
    # MONITOR SPECIFICATIONS
    # ==============================

    screen_size_inch = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    resolution = models.CharField(max_length=50, null=True, blank=True)
    panel_type = models.CharField(max_length=20, choices=PANEL_TYPE_CHOICES, null=True, blank=True)
    touchscreen = models.BooleanField(null=True, blank=True)
    curved_screen = models.BooleanField(null=True, blank=True)
    input_ports = models.JSONField(null=True, blank=True)
    usb_hub_available = models.BooleanField(null=True, blank=True)
    speakers_available = models.BooleanField(null=True, blank=True)

    # ==============================
    # MOUSE / KEYBOARD SPECIFICATIONS
    # ==============================

    connectivity_type = models.CharField(
        max_length=50,
        choices=CONNECTIVITY_CHOICES,
        null=True,
        blank=True
    )

    # ==============================
    # PURCHASE & WARRANTY
    # ==============================

    purchase_date = models.DateField()
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    vendor_name = models.CharField(max_length=150)
    invoice_number = models.CharField(max_length=100, null=True, blank=True)

    warranty_start = models.DateField(null=True, blank=True)
    warranty_end = models.DateField(null=True, blank=True)
    warranty_status = models.CharField(
        max_length=20,
        choices=WARRANTY_STATUS_CHOICES,
        null=True,
        blank=True
    )

    # ==============================
    # DEVICE LIFECYCLE
    # ==============================

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='AVAILABLE'
    )

    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default='NEW'
    )

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    

    assigned_date = models.DateField(null=True, blank=True)
    returned_date = models.DateField(null=True, blank=True)
    current_location = models.CharField(max_length=150, null=True, blank=True)

    # ==============================
    # ADDITIONAL DETAILS
    # ==============================

    attachment = models.FileField(
        upload_to="asset_attachments/",
        null=True,
        blank=True
    )

    warranty_documents = models.FileField(
        upload_to="asset_warranty_docs/",
        null=True,
        blank=True
    )

    remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ==============================
    # AUTO STOCK STATUS LOGIC
    # ==============================

    def save(self, *args, **kwargs):

    # Auto stock status
        if self.available_quantity <= 0:
            self.status = "OUT_OF_STOCK"
        elif self.available_quantity <= self.minimum_stock_level:
            self.status = "LOW_STOCK"
        else:
            self.status = "AVAILABLE"

        super().save(*args, **kwargs)

# describe the asset details
# # Track Asset Issue / Return History
class AssetDetails(models.Model):

    STATUS_CHOICES = (
        ('ISSUED', 'Issued'),
        ('RETURNED', 'Returned'),
        ('DAMAGED', 'Damaged'),
    )

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='issue_records'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assets_received'
    )

    quantity_issued = models.PositiveIntegerField(default=1)

    # issued_date = models.DateTimeField(auto_now_add=True)

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
        on_delete=models.SET_NULL,
        null=True,
        related_name='assets_issued'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # =====================================
    # AUTO STOCK UPDATE LOGIC
    # =====================================

    def save(self, *args, **kwargs):

        if not self.pk:  # Only when creating (issuing)
            if self.asset.available_quantity < self.quantity_issued:
                raise ValueError("Not enough stock available.")

            self.asset.available_quantity -= self.quantity_issued
            self.asset.save()

        elif self.status == "RETURNED" and self.return_date:
            # Add quantity back on return
            self.asset.available_quantity += self.quantity_issued
            self.asset.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.asset.asset_tag} → {self.user}"

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

    TRIGGERED_BY_CHOICES = (
        ("SYSTEM", "System"),
        ("ADMIN", "Admin"),
    )

    # 🔁 Changed from Inventory → Asset
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="purchase_requests"
    )

    request_type = models.CharField(
        max_length=10,
        choices=REQUEST_TYPES
    )

    triggered_by = models.CharField(
        max_length=10,
        choices=TRIGGERED_BY_CHOICES
    )

    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    quantity_needed = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING_FINANCE"
    )

    remarks = models.TextField(blank=True, null=True)

    # Invoice Upload
    invoice_attachment = models.FileField(
        upload_to="purchase_invoices/",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PR-{self.id} | {self.asset.asset_tag}"