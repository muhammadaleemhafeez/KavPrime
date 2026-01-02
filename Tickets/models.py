from django.db import models
from users.models import User   # adjust if your user model name differs
from django.conf import settings
from django.utils import timezone

class Ticket(models.Model):
    TICKET_TYPES = [
        ('repair', 'Repair an item'),
        ('new_item', 'Request a new item'),
        ('general', 'Report a general issue'),
    ]

    # Workflow states
    STATUS_CHOICES = [
        ('PENDING_TEAM_PMO', 'Pending Team PMO'),
        ('PENDING_SENIOR_PMO', 'Pending Senior PMO'),
        ('PENDING_ADMIN', 'Pending Admin'),
        ('REJECTED', 'Rejected'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
    ]

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Dynamic reference to the user model
        on_delete=models.CASCADE,
        related_name='tickets'
    )

    ticket_type = models.CharField(max_length=20, choices=TICKET_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING_TEAM_PMO')

    # New field for team PMO's action deadline (useful for escalation)
    team_pmo_deadline = models.DateTimeField(null=True, blank=True)

    created_by_role = models.CharField(max_length=30, blank=True)  # EMPLOYEE / TEAM_PMO / SENIOR_PMO

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional: To keep track of the escalation history
    escalation_deadline = models.DateTimeField(null=True, blank=True)  # If you want a dedicated escalation deadline

    def __str__(self):
        return f"Ticket {self.id}: {self.title}"

class AssignedTicket(models.Model):
    ACTION_STATUS = [
        ('ASSIGNED', 'Assigned'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('ESCALATED', 'Escalated'),
        ('COMPLETED', 'Completed'),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='history')

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Dynamic reference to the user model
        on_delete=models.CASCADE,
        related_name='assigned_ticket_rows'
    )

    role = models.CharField(max_length=30)  # TEAM_PMO / SENIOR_PMO / ADMIN
    status = models.CharField(max_length=20, choices=ACTION_STATUS, default='ASSIGNED')
    remarks = models.TextField(blank=True)
    action_date = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "assigned_tickets"  # Specify the table name if necessary

    def __str__(self):
        return f"Assigned Ticket {self.ticket.id}: {self.role} - {self.status}"
