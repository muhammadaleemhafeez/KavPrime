from django.urls import path
from . import views

urlpatterns = [

    # ─────────────────────────────────────────
    # ASSET & INVENTORY REPORTS
    # ─────────────────────────────────────────

    # GET /api/reports/assets/summary/
    # Overall counts by status, category, condition, warranty
    path("assets/summary/", views.report_asset_summary, name="report_asset_summary"),

    # GET /api/reports/assets/list/
    # Full asset list — ?category=LAPTOP&status=AVAILABLE&condition=NEW&from_date=&to_date=
    path("assets/list/", views.report_asset_full_list, name="report_asset_full_list"),

    # GET /api/reports/assets/issue-return-history/
    # Full issue/return audit trail — ?asset_id=&employee_id=&status=ISSUED&from_date=&to_date=
    path("assets/issue-return-history/", views.report_asset_issue_return_history, name="report_asset_issue_return_history"),

    # GET /api/reports/assets/currently-issued/
    # All assets still ISSUED (not returned), with days held
    path("assets/currently-issued/", views.report_currently_issued_assets, name="report_currently_issued_assets"),

    # GET /api/reports/assets/low-stock/
    # Assets with LOW_STOCK or OUT_OF_STOCK status
    path("assets/low-stock/", views.report_low_stock_assets, name="report_low_stock_assets"),

    # GET /api/reports/assets/warranty-expiry/
    # Expired or expiring warranties — ?days=30 for next 30 days
    path("assets/warranty-expiry/", views.report_warranty_expiry, name="report_warranty_expiry"),


    # ─────────────────────────────────────────
    # TICKET & WORKFLOW REPORTS
    # ─────────────────────────────────────────

    # GET /api/reports/tickets/summary/
    # Counts by status, type, created_by_role, pending_by_role — ?from_date=&to_date=
    path("tickets/summary/", views.report_ticket_summary, name="report_ticket_summary"),

    # GET /api/reports/tickets/list/
    # Full ticket list — ?status=&ticket_type=&employee_id=&from_date=&to_date=
    path("tickets/list/", views.report_ticket_full_list, name="report_ticket_full_list"),

    # GET /api/reports/tickets/approval-history/
    # Full approve/reject audit trail — ?ticket_id=&role=&status=APPROVED&from_date=&to_date=
    path("tickets/approval-history/", views.report_ticket_approval_history, name="report_ticket_approval_history"),

    # GET /api/reports/tickets/sla-breach/
    # Tickets that missed their SLA deadline and are still open
    path("tickets/sla-breach/", views.report_sla_breach, name="report_sla_breach"),

    # GET /api/reports/tickets/pending-by-role/
    # Count of open tickets grouped by current_role (who needs to act)
    path("tickets/pending-by-role/", views.report_pending_tickets_by_role, name="report_pending_tickets_by_role"),


    # ─────────────────────────────────────────
    # USER & EMPLOYEE REPORTS
    # ─────────────────────────────────────────

    # GET /api/reports/users/summary/
    # Counts by role and employment_status
    path("users/summary/", views.report_user_summary, name="report_user_summary"),

    # GET /api/reports/users/<employee_id>/asset-history/
    # Full lifetime asset issue/return history for one employee
    path("users/<int:employee_id>/asset-history/", views.report_employee_asset_history, name="report_employee_asset_history"),

    # GET /api/reports/users/<employee_id>/offboarding-checklist/
    # Offboarding audit: unreturned assets + open tickets for one employee
    path("users/<int:employee_id>/offboarding-checklist/", views.report_offboarding_checklist, name="report_offboarding_checklist"),

    # GET /api/reports/users/exited/
    # All employees with employment_status=EXITED
    path("users/exited/", views.report_exited_employees, name="report_exited_employees"),


    # ─────────────────────────────────────────
    # PURCHASE & FINANCE REPORTS
    # ─────────────────────────────────────────

    # GET /api/reports/purchases/summary/
    # Purchase request counts by status, type, triggered_by — ?from_date=&to_date=
    path("purchases/summary/", views.report_purchase_summary, name="report_purchase_summary"),

    # GET /api/reports/purchases/list/
    # Full purchase request list — ?status=PENDING_FINANCE&from_date=&to_date=
    path("purchases/list/", views.report_purchase_full_list, name="report_purchase_full_list"),

    # GET /api/reports/purchases/vendor-summary/
    # All vendors with total assets purchased and total spend
    path("purchases/vendor-summary/", views.report_vendor_summary, name="report_vendor_summary"),


    # ─────────────────────────────────────────
    # AUDIT LOG & DASHBOARD
    # ─────────────────────────────────────────

    # GET /api/reports/audit-log/
    # Master audit log: all asset events + ticket events, sorted by time — ?from_date=&to_date=
    path("audit-log/", views.report_audit_log, name="report_audit_log"),

    # GET /api/reports/dashboard-stats/
    # Quick summary stats for a dashboard page (assets, tickets, users, purchases)
    path("dashboard-stats/", views.report_dashboard_stats, name="report_dashboard_stats"),
]