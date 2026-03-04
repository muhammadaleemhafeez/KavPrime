# Tickets/email_utils.py
from django.core.mail import send_mail
from django.conf import settings


def _send(to_email, subject, message):
    if not to_email:
        return
    if isinstance(to_email, str):
        to_email = [to_email]
    to_email = list({e.strip() for e in to_email if e and str(e).strip()})
    if not to_email:
        return
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=to_email,
        fail_silently=False,
    )


def send_ticket_created_email(ticket, assigned_to_user):
    if not assigned_to_user or not assigned_to_user.email:
        return
    _send(
        assigned_to_user.email,
        f"[KavPrime] New Ticket Assigned — #{ticket.id}: {ticket.title}",
        f"""Hello {assigned_to_user.name},

A new ticket has been assigned to you and requires your review.

Ticket ID   : #{ticket.id}
Title       : {ticket.title}
Type        : {ticket.ticket_type}
Description : {ticket.description}
Raised By   : {ticket.employee.name} ({ticket.employee.email})
Your Role   : {ticket.current_role}

This is an automated notification from KavPrime.
"""
    )


def send_ticket_approved_email(ticket, approved_by_user, remarks=""):
    if not ticket.employee or not ticket.employee.email:
        return
    next_step_line = (
        "Your ticket has been fully approved and is now COMPLETED."
        if ticket.status == "COMPLETED"
        else f"Your ticket has been approved and forwarded to: {ticket.current_role}."
    )
    _send(
        ticket.employee.email,
        f"[KavPrime] Ticket Approved — #{ticket.id}: {ticket.title}",
        f"""Hello {ticket.employee.name},

Your ticket has been approved.

Ticket ID   : #{ticket.id}
Title       : {ticket.title}
Approved By : {approved_by_user.name} ({approved_by_user.email})
Remarks     : {remarks if remarks else 'N/A'}

{next_step_line}

This is an automated notification from KavPrime.
"""
    )


def send_ticket_rejected_email(ticket, rejected_by_user, remarks=""):
    if not ticket.employee or not ticket.employee.email:
        return
    _send(
        ticket.employee.email,
        f"[KavPrime] Ticket Rejected — #{ticket.id}: {ticket.title}",
        f"""Hello {ticket.employee.name},

Your ticket has been rejected.

Ticket ID   : #{ticket.id}
Title       : {ticket.title}
Rejected By : {rejected_by_user.name} ({rejected_by_user.email})
Reason      : {remarks if remarks else 'No reason provided'}

This is an automated notification from KavPrime.
"""
    )


def send_ticket_completed_email(ticket):
    if not ticket.employee or not ticket.employee.email:
        return
    _send(
        ticket.employee.email,
        f"[KavPrime] Ticket Completed — #{ticket.id}: {ticket.title}",
        f"""Hello {ticket.employee.name},

Your ticket has been fully processed and is now COMPLETED.

Ticket ID   : #{ticket.id}
Title       : {ticket.title}
Final Status: COMPLETED

This is an automated notification from KavPrime.
"""
    )