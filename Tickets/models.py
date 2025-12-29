from django.db import models
from users.models import User   # adjust if your user model name differs

class Ticket(models.Model):

    TICKET_TYPES = [
        ('repair', 'Repair an item'),
        ('new_item', 'Request a new item'),
        ('general', 'Report a general issue'),
    ]

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
    ]

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tickets'
    )

    ticket_type = models.CharField(max_length=20, choices=TICKET_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ticket_type} - {self.title}"
