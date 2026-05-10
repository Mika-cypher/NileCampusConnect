# core/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random
import string
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
from pgvector.django import VectorField
from django.core.exceptions import ValidationError


class CustomUser(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    """
    bio = models.TextField(
        blank=True,
        default='',
        help_text="A short bio displayed on the public profile page"
    )
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True,
        help_text="Profile avatar shown across the platform"
    )

    @property
    def average_rating(self):
        """
        Returns the mean rating across all reviews received,
        rounded to 1 decimal place. Returns None if no reviews yet.
        """
        reviews = self.reviews_received.all()
        if not reviews.exists():
            return None
        total = sum(r.rating for r in reviews)
        return round(total / reviews.count(), 1)

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"


class Wallet(models.Model):
    """
    One wallet per user. Tracks spendable balance and funds locked in escrow.

    Flow:
      Checkout   → available_balance -= price,  escrow_balance += price
      Complete   → escrow_balance    -= price,  freelancer.available_balance += price
      Cancel     → escrow_balance    -= price,  client.available_balance += price (refund)
    """
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='wallet'
    )
    available_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Funds the user can spend or withdraw (₦)"
    )
    escrow_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Funds locked in active orders, not yet released (₦)"
    )

    def __str__(self):
        return f"{self.user.username}'s wallet — ₦{self.available_balance} available"

    class Meta:
        verbose_name = "Wallet"
        verbose_name_plural = "Wallets"

class Category(models.Model):
    """
    Service categories. Slug is auto-generated from name on save —
    never needs to be set manually.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)

    def save(self, *args, **kwargs):
        # Auto-populate slug from name whenever name changes
        if not self.slug or self._state.adding:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

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
    image = models.ImageField(
        upload_to='services/',
        blank=True,
        null=True,
        help_text="Optional cover image for the service listing"
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.SET_NULL,   
        null=True,
        blank=True,
        related_name='services',
        help_text="The category this service belongs to"
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
    embedding = VectorField(dimensions=768, null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.freelancer.username}"

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"
        ordering = ['-created_at']


class Order(models.Model):
    """
    Order model representing a transaction between a client and a freelancer.
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
    )
    freelancer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='orders_as_freelancer',
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='orders',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Snapshot of the price at time of order (₦)"
    )
    escrow_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount currently locked in escrow for this order (₦)"
    )
    is_funds_in_escrow = models.BooleanField(
        default=False,
        help_text="True while funds are locked; False after release or refund"
    )
    delivery_file = models.FileField(
        upload_to='deliveries/',
        blank=True,
        null=True,
        help_text="The final completed work uploaded by the freelancer"
    )
    delivery_notes = models.TextField(
        blank=True,
        help_text="Notes from the freelancer upon delivery"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} — {self.service.title} [{self.status}]"

    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ['-created_at']

    def get_status_display_class(self):
        """Bootstrap badge class for the order status."""
        return {
            'pending': 'bg-secondary',
            'pending_acceptance': 'bg-info',
            'in_progress': 'bg-warning text-dark',
            'completed': 'bg-success',
            'cancelled': 'bg-danger',
        }.get(self.status, 'bg-secondary')

 # core/models.py
class Review(models.Model):
    """
    One review per completed order, written by the buyer about the freelancer.

    The OneToOneField on `order` is the hard DB constraint — it makes a
    duplicate review literally impossible at the database level, even under
    concurrent requests. No need for a separate unique_together.
    """
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]  # 1 through 5

    order = models.OneToOneField(
        'Order',
        on_delete=models.CASCADE,
        related_name='review',
        help_text="The completed order this review is attached to"
    )
    reviewer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='reviews_given',
        help_text="The buyer who wrote this review"
    )
    reviewee = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='reviews_received',
        help_text="The freelancer being reviewed"
    )
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        help_text="Star rating from 1 (poor) to 5 (excellent)"
    )
    comment = models.TextField(
        blank=True,
        default='',
        help_text="Optional written feedback from the buyer"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.reviewer.username} → {self.reviewee.username}: {self.rating}★"

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        ordering = ['-created_at']

class Message(models.Model):
    """
    A single message between a buyer and freelancer, scoped to an Order.

    Scoping to Order (not User-pair) is intentional: two users could have
    multiple orders together, and keeping threads separate avoids confusion.
    """
    order = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="The order this message belongs to"
    )
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        help_text="The user who sent this message"
    )
    text = models.TextField(
        help_text="Message body"
    )
    is_read = models.BooleanField(
        default=False,
        help_text="True once the recipient has viewed this message. Used for unread counts."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message #{self.id} on Order #{self.order_id} from {self.sender.username}"
    
    def clean(self):
        super().clean() # Always call the parent class first
        
        trigger_words = ['assignment', 'exam', 'quiz', 'homework', 'grade', 'lecturer']
        content_lower = str(self.text).lower()

        # Check if any banned word is in the message
        for word in trigger_words:
            if word in content_lower:
                # This stops the database save and throws an error back to the user
                raise ValidationError(f"Message blocked: The word '{word}' triggers our Academic Integrity filter. Please revise your message.")

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['created_at']   # ascending — reads top-to-bottom like a chat

class Notification(models.Model):
    """
    A single in-app notification for a user.

    `link` stores a relative URL (e.g. '/orders/42/') so templates can
    render <a href="{{ notif.link }}"> without a reverse() call.
    The context processor surfaces the top 5 unread to every template.
    """
    recipient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="The user who receives this notification"
    )
    message = models.CharField(
        max_length=255,
        help_text="Short human-readable description of the event"
    )
    link = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="Relative URL the notification links to (e.g. /orders/42/)"
    )
    is_read = models.BooleanField(
        default=False,
        help_text="Marked True once the user has seen this notification"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"→ {self.recipient.username}: {self.message[:60]}"

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']   #

class OTP(models.Model):
    """
    Stores a short-lived 6-digit code for email verification.
    Automatically expires 10 minutes after creation.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='otp_record'
    )
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    @staticmethod
    def generate_code():
        """Generates a secure, random 6-digit string."""
        return ''.join(random.choices(string.digits, k=6))

    def is_expired(self):
        """Checks if the current time is past the expiration time."""
        return timezone.now() > self.expires_at

    def save(self, *args, **kwargs):
        """Auto-calculate the expiration time if it doesn't exist."""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"OTP for {self.user.username} (Valid: {not self.is_expired()})"