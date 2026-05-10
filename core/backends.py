from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class EmailBackend(ModelBackend):
    """
    Custom authentication backend that allows users to login with their email address.
    Bulletproofed for case-insensitivity and duplicate test accounts.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('username')
        
        if username is None or password is None:
            return None
        
        # 1. Check if it's an email
        if '@' in username:
            # Use 'iexact' to ignore uppercase/lowercase differences
            users = User.objects.filter(email__iexact=username)
            
            if not users.exists():
                return None
                
            # If multiple exist (common in testing), grab the active one first
            if users.count() > 1:
                user = users.filter(is_active=True).first()
                # If none are active, just grab the first one to show the standard error
                if not user:
                    user = users.first()
            else:
                user = users.first()
                
        else:
            # 2. Doesn't look like an email, try username
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                return None
        
        # 3. Check the password AND ensure the account is active
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None