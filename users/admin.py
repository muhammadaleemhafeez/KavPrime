# users/admin.py
from django.contrib import admin
from .models import User, Role

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "role", "role_obj", "is_active", "is_staff")
    search_fields = ("email", "name")
    list_filter = ("is_active", "is_staff", "role")
