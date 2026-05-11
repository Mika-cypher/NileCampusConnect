from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import requests # <-- Added this to fix the bug
import base64
from email.mime.text import MIMEText

def get_gmail_access_token():
    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": settings.GOOGLE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")

def send_otp_email(user, otp_code):
    access_token = get_gmail_access_token()
    
    subject = "Verify your Nile Campus Connect account"
    html_content = render_to_string('core/otp_email.html', {'user': user, 'otp_code': otp_code})
    
    message = MIMEText(html_content, 'html')
    message['to'] = user.email
    message['from'] = settings.EMAIL_HOST_USER
    message['subject'] = subject
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    requests.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"raw": raw}
    )