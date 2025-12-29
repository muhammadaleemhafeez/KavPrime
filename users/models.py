from django.db import models

class User(models.Model):

    ROLE_CHOICES = [
        ('EMPLOYEE', 'Employee'),
        ('PMO', 'PMO'),
        ('ADMIN', 'Admin'),
        ('FINANCE', 'Finance'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='EMPLOYEE'
    )

    def __str__(self):
        return f"{self.email} - {self.role}"
