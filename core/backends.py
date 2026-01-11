from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Custom authentication backend that allows users to login with their email address.
    Falls back to username authentication if the input doesn't look like an email.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a user by email or username.
        
        Args:
            request: The HTTP request object
            username: Can be either username or email address
            password: User's password
            
        Returns:
            User object if authentication succeeds, None otherwise
        """
        if username is None:
            username = kwargs.get('username')
        
        if username is None or password is None:
            return None
        
        # Check if the username parameter looks like an email
        if '@' in username:
            try:
                # Try to find a user with this email
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                # No user found with this email, return None
                return None
            except User.MultipleObjectsReturned:
                # Multiple users with same email (shouldn't happen, but handle it)
                user = User.objects.filter(email=username).first()
        else:
            # Doesn't look like an email, try username authentication
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return None
        
        # Check the password
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None

