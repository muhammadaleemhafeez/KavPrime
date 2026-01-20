# users/models.py
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin
)

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g. EMPLOYEE, TEAM_PMO, HR
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ("EMPLOYEE", "Employee"),
        ("TEAM_PMO", "Team PMO"),
        ("SENIOR_PMO", "Senior PMO"),
        ("ADMIN", "Admin"),
        ("FINANCE", "Finance"),
        ("HR", "HR"),
    ]

    EMPLOYMENT_STATUS_CHOICES = [
        ("ONBOARDING", "Onboarding"),
        ("ACTIVE", "Active"),
        ("OFFBOARDING", "Offboarding"),
        ("EXITED", "Exited"),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)

    # ✅ Keep existing role field (so old code keeps working)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="EMPLOYEE",
    )

    # ✅ NEW: Dynamic role reference (Admin can add roles)
    role_obj = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # For storing the employee's designation
    designation = models.CharField(max_length=100, blank=True, null=True)  

    # For storing the employee's image
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)  

    # ✅ NEW (minimal onboarding/offboarding)
    employment_status = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_STATUS_CHOICES,
        default="ONBOARDING"
    )
    join_date = models.DateField(null=True, blank=True)
    exit_date = models.DateField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def __str__(self):
        return f"{self.email} - {self.role_name}"

    @property
    def role_name(self):
        # Prefer dynamic role if present, else fallback to old string role
        return self.role_obj.name if self.role_obj else self.role

    def save(self, *args, **kwargs):
        # ✅ Auto-create Role if role_obj not set but role string exists
        if not self.role_obj and self.role:
            role_rec, _ = Role.objects.get_or_create(name=self.role)
            self.role_obj = role_rec
        super().save(*args, **kwargs)
