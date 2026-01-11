from django.db import models
from django.contrib.auth.models import AbstractUser
from decimal import Decimal


class CustomUser(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Includes wallet_balance field to support the dashboard wallet card.
    """
    wallet_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="User's wallet balance in Nigerian Naira (₦)"
    )
    
    def __str__(self):
        return self.username
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"


class Service(models.Model):
    """
    Service/Gig model representing services offered by freelancers.
    """
    title = models.CharField(
        max_length=200,
        help_text="Title of the service/gig"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price of the service in Nigerian Naira (₦)"
    )
    description = models.TextField(
        help_text="Detailed description of the service"
    )
    delivery_time = models.CharField(
        max_length=100,
        help_text="Expected delivery time (e.g., '2 days', '1 week')"
    )
    freelancer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='services',
        help_text="The freelancer offering this service"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the service is currently available"
    )
    
    def __str__(self):
        return f"{self.title} - {self.freelancer.username}"
    
    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"
        ordering = ['-created_at']


class Order(models.Model):
    """
    Order model representing transactions between clients and freelancers.
    Supports the 'Active Orders' table in the dashboard.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('pending_acceptance', 'Pending Acceptance'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    client = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='orders_as_client',
        help_text="The client who placed the order"
    )
    freelancer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='orders_as_freelancer',
        help_text="The freelancer working on the order"
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='orders',
        help_text="The service being ordered"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current status of the order"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price of the order in Nigerian Naira (₦)"
    )
    escrow_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount held in escrow for this order (for Mock Payment system)"
    )
    is_funds_in_escrow = models.BooleanField(
        default=False,
        help_text="Whether funds are currently held in escrow"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Order #{self.id} - {self.service.title} - {self.status}"
    
    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ['-created_at']
        
    def get_status_display_class(self):
        """
        Helper method to return Bootstrap badge class for status display.
        Useful for rendering status badges in templates.
        """
        status_classes = {
            'pending': 'badge-secondary',
            'pending_acceptance': 'badge-info',
            'in_progress': 'badge-warning',
            'completed': 'badge-success',
            'cancelled': 'badge-danger',
        }
        return status_classes.get(self.status, 'badge-secondary')

