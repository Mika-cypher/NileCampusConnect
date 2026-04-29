# core/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Max
from django.utils import timezone
from django.core.paginator import Paginator
from django.conf import settings
from .models import Order, Service, Wallet, CustomUser, Review, Category, Message, Notification
from .forms import StudentRegistrationForm, ServiceForm, DeliveryForm, ReviewForm, ProfileUpdateForm, MessageForm


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    active_orders = Order.objects.filter(
        client=request.user,
        status__in=['pending', 'in_progress', 'pending_acceptance']
    ).order_by('-created_at')

    completed_orders = Order.objects.filter(
        client=request.user,
        status__in=['completed', 'cancelled']
    ).order_by('-updated_at')

    incoming_jobs = Order.objects.filter(
        freelancer=request.user,
        status__in=['pending', 'in_progress', 'pending_acceptance']
    ).order_by('-created_at')

    completed_jobs = Order.objects.filter(
        freelancer=request.user,
        status__in=['completed', 'cancelled']
    ).order_by('-updated_at')

    services = Service.objects.filter(freelancer=request.user)

    return render(request, 'core/dashboard.html', {
        'wallet': wallet,
        'active_orders': active_orders,
        'completed_orders': completed_orders,
        'incoming_jobs': incoming_jobs,
        'completed_jobs': completed_jobs,
        'services': services,
        'PAYSTACK_PUBLIC_KEY': settings.PAYSTACK_PUBLIC_KEY,
    })


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def register(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('core:dashboard')
    else:
        form = StudentRegistrationForm()
    return render(request, 'core/register.html', {'form': form})


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

@login_required
def create_service(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save(commit=False)
            service.freelancer = request.user
            service.save()
            messages.success(request, "Your gig has been posted!")
            return redirect('core:dashboard')
    else:
        form = ServiceForm()
    return render(request, 'core/create_service.html', {'form': form})


def marketplace(request):
    services = Service.objects.filter(
        is_active=True
    ).select_related('freelancer', 'category').order_by('-created_at')
    # ── PAGINATION LOGIC ──
    # Show 9 gigs per page (creates a clean 3x3 grid on desktop)
    paginator = Paginator(services, 9) 
    page_number = request.GET.get('page')
    services = paginator.get_page(page_number)

    # --- Text search ---
    search_query = request.GET.get('q', '').strip()
    if search_query:
        services = services.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # --- Category filter ---
    category_slug = request.GET.get('category', '').strip()
    active_category = None
    if category_slug:
        active_category = Category.objects.filter(slug=category_slug).first()
        if active_category:
            services = services.filter(category=active_category)

    # --- Price range filter ---
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    try:
        if min_price:
            services = services.filter(price__gte=min_price)
    except (ValueError, TypeError):
        min_price = ''
    try:
        if max_price:
            services = services.filter(price__lte=max_price)
    except (ValueError, TypeError):
        max_price = ''

    all_categories = Category.objects.all()

    return render(request, 'core/marketplace.html', {
        'services':        services,
        'search_query':    search_query,
        'all_categories':  all_categories,
        'active_category': active_category,
        'min_price':       min_price,
        'max_price':       max_price,
    })


def service_detail(request, pk):
    service = get_object_or_404(Service, pk=pk)
    return render(request, 'core/service_detail.html', {'service': service})


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

@login_required
def checkout(request, pk):
    service = get_object_or_404(Service, pk=pk)

    if request.user == service.freelancer:
        messages.error(request, "You can't purchase your own service.")
        return redirect('core:service_detail', pk=pk)

    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        if wallet.available_balance < service.price:
            messages.error(
                request,
                f"Insufficient funds. Your balance is ₦{wallet.available_balance:,.2f} "
                f"but this service costs ₦{service.price:,.2f}."
            )
            return redirect('core:checkout', pk=pk)

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            if wallet.available_balance < service.price:
                messages.error(request, "Insufficient funds.")
                return redirect('core:checkout', pk=pk)

            wallet.available_balance -= service.price
            wallet.escrow_balance    += service.price
            wallet.save()

            order = Order.objects.create(
                client=request.user,
                freelancer=service.freelancer,
                service=service,
                status='pending',
                price=service.price,
                escrow_amount=service.price,
                is_funds_in_escrow=True,
            )

            Notification.objects.create(
                recipient=service.freelancer,
                message=f"New order: {request.user.username} purchased '{service.title}'.",
                link=f"/orders/{order.pk}/",
            )

        messages.success(
            request,
            f"Order placed! ₦{service.price:,.2f} is held in escrow until you accept delivery."
        )
        return redirect('core:order_detail', pk=order.pk)

    return render(request, 'core/checkout.html', {
        'service': service,
        'wallet': wallet,
        'can_afford': wallet.available_balance >= service.price,
    })


# ---------------------------------------------------------------------------
# Order detail — status updates and escrow release live here
@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)

    # Only the buyer or seller may access this page
    if request.user != order.client and request.user != order.freelancer:
        messages.error(request, "You don't have permission to view this order.")
        return redirect('core:dashboard')

    if request.method == 'POST':

        # ── Branch 1: sending a message ──────────────────────────────────
        if 'send_message' in request.POST:
            msg_form = MessageForm(request.POST)
            if msg_form.is_valid():
                message = msg_form.save(commit=False)
                message.order  = order
                message.sender = request.user
                message.save()
                # Mark all messages from the other party as read,
                # since the user is clearly looking at the thread right now.
                order.messages.exclude(sender=request.user).update(is_read=True)
            # Redirect to prevent double-POST on browser refresh
            return redirect('core:order_detail', pk=pk)

        # ── Branch 2: order status actions ───────────────────────────────
        action = request.POST.get('action')

        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=pk)

            # --- Freelancer actions ---
            if request.user == order.freelancer:
                if action == 'accept' and order.status == 'pending':
                    order.status = 'in_progress'
                    order.save()
                    messages.success(request, "You've accepted the order. Get to work!")

                elif action == 'cancel' and order.status in ('pending', 'in_progress'):
                    if order.is_funds_in_escrow:
                        buyer_wallet = Wallet.objects.select_for_update().get(user=order.client)
                        buyer_wallet.available_balance += order.escrow_amount
                        buyer_wallet.escrow_balance    -= order.escrow_amount
                        buyer_wallet.save()
                        order.escrow_amount      = 0
                        order.is_funds_in_escrow = False

                    order.status = 'cancelled'
                    order.save()
                    messages.warning(request, "Order cancelled. The buyer has been refunded.")

            # --- Buyer actions ---
            elif request.user == order.client:
                if action == 'complete' and order.status == 'pending_acceptance':
                    if order.is_funds_in_escrow:
                        buyer_wallet      = Wallet.objects.select_for_update().get(user=order.client)
                        freelancer_wallet = Wallet.objects.select_for_update().get(user=order.freelancer)

                        buyer_wallet.escrow_balance        -= order.escrow_amount
                        freelancer_wallet.available_balance += order.escrow_amount
                        buyer_wallet.save()
                        freelancer_wallet.save()

                        order.escrow_amount      = 0
                        order.is_funds_in_escrow = False

                    order.status = 'completed'
                    order.save()
                    messages.success(
                        request,
                        f"Delivery accepted! ₦{order.price:,.2f} released to {order.freelancer.username}."
                    )

        return redirect('core:order_detail', pk=pk)

    # ── GET ──────────────────────────────────────────────────────────────
    # Fetch thread and mark incoming messages as read in one query
    thread = order.messages.select_related('sender').all()
    order.messages.exclude(sender=request.user).update(is_read=True)

    msg_form = MessageForm()

    return render(request, 'core/order_detail.html', {
        'order':    order,
        'thread':   thread,
        'msg_form': msg_form,
    })


# ---------------------------------------------------------------------------
# Delivery — freelancer submits work, status moves to pending_acceptance
# ---------------------------------------------------------------------------

@login_required
def deliver_order(request, pk):
    order = get_object_or_404(Order, pk=pk)

    # Only the freelancer on this order may access this view
    if request.user != order.freelancer:
        messages.error(request, "Only the freelancer on this order can submit a delivery.")
        return redirect('core:order_detail', pk=pk)

    # Can only deliver an order that is actively in progress
    if order.status != 'in_progress':
        messages.error(request, "This order is not currently in progress and cannot be delivered.")
        return redirect('core:order_detail', pk=pk)

    if request.method == 'POST':
        form = DeliveryForm(request.POST, request.FILES, instance=order)
        if form.is_valid():
            delivery = form.save(commit=False)
            delivery.status       = 'pending_acceptance'
            delivery.delivered_at = timezone.now()
            delivery.save()
            messages.success(
                request,
                f"Delivery submitted! {order.client.username} will now review your work and release payment."
            )
            return redirect('core:order_detail', pk=pk)
    else:
        form = DeliveryForm(instance=order)

    return render(request, 'core/deliver_order.html', {
        'order': order,
        'form': form,
    })


# ─────────────────────────────────────────────────────────────
# Public profile — visible to anyone, logged in or not
# ─────────────────────────────────────────────────────────────

def public_profile(request, username):
    """
    Anyone can view a user's public profile page.
    Shows: bio, avatar, active gigs (if freelancer), and all reviews received.
    """
    profile_user = get_object_or_404(CustomUser, username=username)

    active_services = Service.objects.filter(
        freelancer=profile_user,
        is_active=True
    ).order_by('-created_at')

    reviews = Review.objects.filter(
        reviewee=profile_user
    ).select_related('reviewer', 'order__service').order_by('-created_at')

    # Check if the logged-in user has any completed orders with this freelancer
    # that haven't been reviewed yet — used to surface a "Leave a Review" prompt.
    reviewable_orders = []
    if request.user.is_authenticated and request.user != profile_user:
        reviewable_orders = Order.objects.filter(
            client=request.user,
            freelancer=profile_user,
            status='completed',
        ).exclude(review__isnull=False)   # exclude orders that already have a review

    context = {
        'profile_user':      profile_user,
        'active_services':   active_services,
        'reviews':           reviews,
        'reviewable_orders': reviewable_orders,
    }
    return render(request, 'core/profile.html', context)


# ─────────────────────────────────────────────────────────────
# Edit profile — private, logged-in user only
# ─────────────────────────────────────────────────────────────

@login_required
def edit_profile(request):
    """
    The logged-in user updates their own bio and profile picture.
    """
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('core:public_profile', username=request.user.username)
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(request, 'core/edit_profile.html', {'form': form})


# ─────────────────────────────────────────────────────────────
# Leave a review — buyer only, completed orders, one per order
# ─────────────────────────────────────────────────────────────

@login_required
def leave_review(request, order_id):
    """
    Only the buyer (client) of a completed order may leave a review.
    The OneToOne on Review.order means the DB rejects a second attempt,
    but we check first to show a clean error instead of a 500.
    """
    order = get_object_or_404(Order, pk=order_id)

    # ── Guard 1: only the buyer ──
    if request.user != order.client:
        messages.error(request, "Only the buyer on this order can leave a review.")
        return redirect('core:order_detail', pk=order_id)

    # ── Guard 2: order must be completed ──
    if order.status != 'completed':
        messages.error(request, "You can only review a completed order.")
        return redirect('core:order_detail', pk=order_id)

    # ── Guard 3: review doesn't already exist ──
    if hasattr(order, 'review'):
        messages.info(request, "You've already left a review for this order.")
        return redirect('core:public_profile', username=order.freelancer.username)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.order    = order
            review.reviewer = request.user
            review.reviewee = order.freelancer
            review.save()
            messages.success(
                request,
                f"Review submitted! Thanks for rating {order.freelancer.username}."
            )
            return redirect('core:public_profile', username=order.freelancer.username)
    else:
        form = ReviewForm()

    return render(request, 'core/leave_review.html', {
        'form':  form,
        'order': order,
    })

@login_required
def edit_service(request, pk):
    service = get_object_or_404(Service, pk=pk)

    # Only the freelancer who owns this gig may edit it
    if request.user != service.freelancer:
        messages.error(request, "You don't have permission to edit this service.")
        return redirect('core:service_detail', pk=pk)

    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, "Your gig has been updated.")
            return redirect('core:service_detail', pk=pk)
    else:
        form = ServiceForm(instance=service)

    return render(request, 'core/edit_service.html', {
        'form':    form,
        'service': service,
    })


# ─────────────────────────────────────────────────────────────
# Delete service — owner only, guarded against active orders
# ─────────────────────────────────────────────────────────────

@login_required
def delete_service(request, pk):
    service = get_object_or_404(Service, pk=pk)

    # Only the owner may delete
    if request.user != service.freelancer:
        messages.error(request, "You don't have permission to delete this service.")
        return redirect('core:service_detail', pk=pk)

    if request.method == 'POST':
        # Guard: block deletion if there are any non-terminal orders on this gig
        active_order_count = service.orders.filter(
            status__in=['pending', 'in_progress', 'pending_acceptance']
        ).count()

        if active_order_count > 0:
            messages.error(
                request,
                f"This gig has {active_order_count} active order(s) and cannot be deleted. "
                "Wait for all orders to complete or be cancelled first."
            )
            return redirect('core:service_detail', pk=pk)

        service.delete()
        messages.success(request, f'"{service.title}" has been deleted.')
        return redirect('core:dashboard')

    # GET — show confirmation page
    active_order_count = service.orders.filter(
        status__in=['pending', 'in_progress', 'pending_acceptance']
    ).count()

    return render(request, 'core/delete_service.html', {
        'service':           service,
        'active_order_count': active_order_count,
    })

@login_required
def mark_notifications_read(request):
    """
    POST-only view. Marks every unread Notification for the current user
    as read in a single UPDATE query, then bounces them to the dashboard.
    Accepts GET too (for safety) — a plain redirect is fine either way.
    """
    Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(is_read=True)

    messages.success(request, "All notifications marked as read.")
    return redirect('core:dashboard')


# ─────────────────────────────────────────────────────────────
# Landing Page (Dual-Sided for Nile Campus Connect)
# ─────────────────────────────────────────────────────────────
def home(request):
    """
    Public landing page. Authenticated users are bounced straight to
    their dashboard — they never need to see the marketing page again.
    """
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    service_count = Service.objects.filter(is_active=True).count()
    user_count    = CustomUser.objects.count()
    featured      = Service.objects.filter(is_active=True).select_related(
                        'freelancer', 'category'
                    ).order_by('-created_at')[:6]

    return render(request, 'core/home.html', {
        'service_count': service_count,
        'user_count':    user_count,
        'featured':      featured,
    })

# ─────────────────────────────────────────────────────────────
# Dedicated Inbox
# ─────────────────────────────────────────────────────────────
@login_required
def inbox(request):
    """
    Lists every order thread the user is a part of that contains
    at least one message. Sorted by most recently active thread first.
    """
    threads = (
        Order.objects
        .filter(
            Q(client=request.user) | Q(freelancer=request.user),
            messages__isnull=False,
        )
        .annotate(latest_message_at=Max('messages__created_at'))
        .select_related('client', 'freelancer', 'service')
        .distinct()
        .order_by('-latest_message_at')
    )

    # Unread count per thread for badge display
    unread_per_thread = {}
    for thread in threads:
        unread_per_thread[thread.pk] = thread.messages.filter(
            is_read=False
        ).exclude(sender=request.user).count()

    # Zip together so template gets one iterable
    thread_data = [
        {
            'order':   t,
            'unread':  unread_per_thread.get(t.pk, 0),
            'other':   t.freelancer if request.user == t.client else t.client,
        }
        for t in threads
    ]

    return render(request, 'core/inbox.html', {'thread_data': thread_data})

# ─────────────────────────────────────────────────────────────
# The "Two Portals" Dashboard
# ─────────────────────────────────────────────────────────────
@login_required
def dashboard(request):
    """
    Splits the user's data into Buying and Selling categories so the 
    template can render a clean, two-portal UI.
    """
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    # === BUYING PORTAL DATA ===
    active_purchases = Order.objects.filter(
        client=request.user,
        status__in=['pending', 'in_progress', 'pending_acceptance']
    ).select_related('service', 'freelancer').order_by('-created_at')

    past_purchases = Order.objects.filter(
        client=request.user,
        status__in=['completed', 'cancelled']
    ).select_related('service', 'freelancer').order_by('-updated_at')

    # === SELLING PORTAL DATA ===
    active_sales = Order.objects.filter(
        freelancer=request.user,
        status__in=['pending', 'in_progress', 'pending_acceptance']
    ).select_related('service', 'client').order_by('-created_at')

    past_sales = Order.objects.filter(
        freelancer=request.user,
        status__in=['completed', 'cancelled']
    ).select_related('service', 'client').order_by('-updated_at')
    
    my_services = Service.objects.filter(freelancer=request.user).order_by('-created_at')

    context = {
        'wallet': wallet,
        'active_purchases': active_purchases,
        'past_purchases': past_purchases,
        'active_sales': active_sales,
        'past_sales': past_sales,
        'my_services': my_services,
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def accept_order(request, pk):
    """Allows the freelancer to accept a pending job and move it to in_progress."""
    order = get_object_or_404(Order, pk=pk, freelancer=request.user, status='pending')
    
    if request.method == 'POST':
        order.status = 'in_progress'
        order.save()
        
        # Notify the buyer that work has started
        Notification.objects.create(
            recipient=order.client,
            message=f"{request.user.username} has started working on your order!",
            link=f"/orders/{order.pk}/"
        )
        messages.success(request, "Job accepted! You can now start working.")
        
    return redirect('core:order_detail', pk=pk)