from django.contrib import admin
from django.contrib import messages
from django.urls import reverse
from decimal import Decimal
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Service, Category, Wallet, Order, Review, Message, Notification

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin config for the custom user model."""
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_wallet_balance', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    fieldsets = UserAdmin.fieldsets
    add_fieldsets = UserAdmin.add_fieldsets

    def get_wallet_balance(self, obj):
        if hasattr(obj, 'wallet'):
            return f"₦{obj.wallet.available_balance}"
        return "No Wallet"
    get_wallet_balance.short_description = 'Wallet Balance'

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    """Admin config for the Wallet model."""
    list_display = ('user', 'available_balance', 'escrow_balance')
    search_fields = ('user__username', 'user__email')
    # This allows you to quickly edit money directly from the list view!
    list_editable = ('available_balance', 'escrow_balance') 

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    """Admin config for the Service model."""
    list_display = ('title', 'freelancer', 'category', 'price', 'delivery_time', 'is_active', 'created_at')
    list_filter  = ('is_active', 'category', 'created_at')
    search_fields = ('title', 'description', 'freelancer__username')
    list_editable = ('is_active',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

# --- DISPUTE RESOLUTION ACTIONS ---

@admin.action(description="Settle Dispute: Refund Client")
def refund_client_action(modeladmin, request, queryset):
    """
    Resolves dispute in favor of the client.
    Refunds the escrow amount back to the client's available balance and cancels the order.
    """
    success_count = 0
    for order in queryset:
        if order.is_funds_in_escrow and order.status != 'cancelled':
            client_wallet = order.client.wallet
            
            # Math based on Wallet model logic
            client_wallet.escrow_balance -= order.escrow_amount
            client_wallet.available_balance += order.escrow_amount
            client_wallet.save()
            
            # Update Order
            order.is_funds_in_escrow = False
            order.escrow_amount = Decimal('0.00')
            order.status = 'cancelled'
            order.save() 
            
            success_count += 1
            
    modeladmin.message_user(
        request, 
        f"Successfully refunded the client for {success_count} order(s).", 
        messages.SUCCESS
    )

@admin.action(description="Settle Dispute: Pay Freelancer")
def pay_freelancer_action(modeladmin, request, queryset):
    """
    Resolves dispute in favor of the freelancer.
    Releases the escrow amount to the freelancer's available balance and completes the order.
    """
    success_count = 0
    for order in queryset:
        if order.is_funds_in_escrow and order.status != 'completed':
            client_wallet = order.client.wallet
            freelancer_wallet = order.freelancer.wallet
            
            # Math based on Wallet model logic
            client_wallet.escrow_balance -= order.escrow_amount
            client_wallet.save()
            
            freelancer_wallet.available_balance += order.escrow_amount
            freelancer_wallet.save()
            
            # Update Order
            order.is_funds_in_escrow = False
            order.escrow_amount = Decimal('0.00')
            order.status = 'completed'
            order.save() 
            
            success_count += 1

    modeladmin.message_user(
        request, 
        f"Successfully released funds to the freelancer for {success_count} order(s).", 
        messages.SUCCESS
    )

# --- MODEL ADMIN REGISTRATION ---

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin config for the Order model."""
    list_display = ('id', 'service', 'client', 'freelancer', 'status', 'price', 'is_funds_in_escrow', 'created_at')
    list_filter = ('status', 'is_funds_in_escrow', 'created_at')
    search_fields = ('service__title', 'client__username', 'freelancer__username')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    # Register the custom actions here
    actions = [refund_client_action, pay_freelancer_action]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('service', 'client', 'freelancer')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}  # auto-fills slug in admin form too

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'order', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('text', 'sender__username', 'order__id')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ('recipient', 'message_preview', 'is_read', 'created_at')
    list_filter   = ('is_read', 'created_at')
    search_fields = ('recipient__username', 'message')
    list_editable = ('is_read',)
    ordering      = ('-created_at',)
    readonly_fields = ('created_at',)

    def message_preview(self, obj):
        return obj.message[:70] + '…' if len(obj.message) > 70 else obj.message
    message_preview.short_description = 'Message'
