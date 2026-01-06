from django.db import models
from django.conf import settings
from django.utils import timezone


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

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="PENDING_TEAM_PMO",
        db_index=True,
    )

    # TEAM PMO must act before this deadline, otherwise auto-escalate
    team_pmo_deadline = models.DateTimeField(null=True, blank=True, db_index=True)

    created_by_role = models.CharField(max_length=30, blank=True)  # EMPLOYEE / TEAM_PMO / SENIOR_PMO

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional
    escalation_deadline = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tickets_ticket"  # optional; remove if you want Django default
        indexes = [
            models.Index(fields=["status", "team_pmo_deadline"]),
            models.Index(fields=["employee"]),
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
        ("STATUS_UPDATED", "Status Updated"),   # added (useful for logging changes)
        ("AUTO_ESCALATED", "Auto Escalated"),   # added (for 4-hour auto shift)
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

    role = models.CharField(max_length=30)  # TEAM_PMO / SENIOR_PMO / ADMIN

    status = models.CharField(
        max_length=20,
        choices=ACTION_STATUS,
        default="ASSIGNED",
        db_index=True,
    )

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
