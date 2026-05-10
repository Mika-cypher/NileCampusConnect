from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings # <-- Added this to fix the bug

def send_otp_email(user, otp_code):
    subject = 'Verify your Nile Campus Connect account'
    
    # 1. The Text Fallback (Crucial for bypassing Spam filters!)
    plain_message = f'Your Nile Campus Connect OTP code is: {otp_code}'
    
    # Renders the nice HTML template
    html_message = render_to_string('core/otp_email.html', {
        'user': user,
        'otp_code': otp_code,
    })
    
    # Sends the email using your settings
    send_mail(
        subject, 
        plain_message, # <-- Replaced the empty string!
        settings.DEFAULT_FROM_EMAIL, 
        [user.email], 
        html_message=html_message,
        fail_silently=False # <-- Forces Django to crash if Google rejects it
    )