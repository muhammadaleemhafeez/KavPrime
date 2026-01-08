# Tickets/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

from users.models import Role


class Workflow(models.Model):
    ticket_type = models.CharField(max_length=50, default="DEFAULT")  # repair/new_item/general or DEFAULT
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("ticket_type", "version")

    def __str__(self):
        return f"{self.ticket_type} v{self.version} {'(ACTIVE)' if self.is_active else ''}"


class WorkflowStep(models.Model):
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="steps")
    step_order = models.PositiveIntegerField()
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    sla_hours = models.PositiveIntegerField(default=4)

    class Meta:
        unique_together = ("workflow", "step_order")
        ordering = ["step_order"]

    def __str__(self):
        return f"{self.workflow} | Step {self.step_order} -> {self.role.name} (SLA {self.sla_hours}h)"


class Ticket(models.Model):
    TICKET_TYPES = [
        ("repair", "Repair an item"),
        ("new_item", "Request a new item"),
        ("general", "Report a general issue"),
    ]

    STATUS_CHOICES = [
        ("PENDING_TEAM_PMO", "Pending Team PMO"),
        ("PENDING_SENIOR_PMO", "Pending Senior PMO"),
        ("PENDING_ADMIN", "Pending Admin"),
        ("REJECTED", "Rejected"),
        ("APPROVED", "Approved"),
        ("COMPLETED", "Completed"),
    ]

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
    )

    ticket_type = models.CharField(max_length=20, choices=TICKET_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()

    # ✅ keep current status system intact for now
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="PENDING_TEAM_PMO",
        db_index=True,
    )

    team_pmo_deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    created_by_role = models.CharField(max_length=30, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    escalation_deadline = models.DateTimeField(null=True, blank=True)

    # ✅ NEW: Assigned_to field (linking the ticket to a user)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,  # Set to null if the assigned user is deleted
        related_name="assigned_tickets",  # A reverse relation from the User model
        null=True,
        blank=True,
    )

    # ✅ NEW (dynamic workflow fields - safe)
    workflow = models.ForeignKey(Workflow, on_delete=models.PROTECT, null=True, blank=True)
    current_step = models.PositiveIntegerField(default=0)  # 0 means "not using workflow yet"
    step_deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    current_role = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "tickets_ticket"
        indexes = [
            models.Index(fields=["status", "team_pmo_deadline"]),
            models.Index(fields=["employee"]),
            models.Index(fields=["step_deadline"]),
        ]

    def __str__(self):
        return f"Ticket {self.id}: {self.title}"


class AssignedTicket(models.Model):
    ACTION_STATUS = [
        ("ASSIGNED", "Assigned"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("ESCALATED", "Escalated"),
        ("COMPLETED", "Completed"),
        ("STATUS_UPDATED", "Status Updated"),
        ("AUTO_ESCALATED", "Auto Escalated"),
    ]

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="history",
        db_index=True,
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assigned_ticket_rows",
        db_index=True,
    )

    role = models.CharField(max_length=30)  # store role name text (safe)
    status = models.CharField(max_length=20, choices=ACTION_STATUS, default="ASSIGNED", db_index=True)

    remarks = models.TextField(blank=True)
    action_date = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "assigned_tickets"
        indexes = [
            models.Index(fields=["ticket", "action_date"]),
            models.Index(fields=["assigned_to", "action_date"]),
        ]

    def __str__(self):
        return f"AssignedTicket {self.id}: Ticket#{self.ticket_id} -> User#{self.assigned_to_id} ({self.role})"
