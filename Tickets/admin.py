# Tickets/admin.py
from django.contrib import admin
from .models import Ticket, Workflow, WorkflowStep

class WorkflowStepInline(admin.TabularInline):
    model = WorkflowStep
    extra = 0

@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ("ticket_type", "version", "is_active", "created_at")
    list_filter = ("ticket_type", "is_active")
    inlines = [WorkflowStepInline]

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket_type", "status", "employee", "workflow", "current_step", "current_role", "created_at")
    list_filter = ("ticket_type", "status")
    search_fields = ("title", "employee__email")
