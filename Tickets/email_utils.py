# Tickets/email_utils.py
from django.core.mail import send_mail

def send_email(to_email, subject, message):
    send_mail(
        subject,
        message,
        'your_email@example.com',  # Replace with your email
        [to_email],
        fail_silently=False,
    )
