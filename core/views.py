# core/views.py

import json
import requests
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.db import transaction, models
from django.db.models import Q, Max, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from django.conf import settings
from .models import Order, Service, Wallet, CustomUser, Review, Category, Message, Notification, OTP
from .forms import StudentRegistrationForm, ServiceForm, DeliveryForm, ReviewForm, ProfileUpdateForm, MessageForm
from decimal import Decimal
from .utils import send_otp_email
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count
from pgvector.django import L2Distance
import google.generativeai as genai
from django.core.mail import send_mail

genai.configure(api_key=settings.GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


# ---------------------------------------------------------------------------
# Public: Home / Landing
# ---------------------------------------------------------------------------

def home(request):
    if request.user.is_authenticated:
        return redirect('core:marketplace')

    service_count = Service.objects.filter(is_active=True).count()
    user_count    = CustomUser.objects.count()
    featured      = (
        Service.objects
        .filter(is_active=True)
        .select_related('freelancer', 'category')
        .order_by('-created_at')[:6]
    )
    return render(request, 'core/home.html', {
        'service_count': service_count,
        'user_count':    user_count,
        'featured':      featured,
    })


# ---------------------------------------------------------------------------
# Public: Marketplace
# ---------------------------------------------------------------------------

def marketplace(request):
    # 1. Start with all active gigs (Notice we removed the order_by here)
    qs = (
        Service.objects
        .filter(is_active=True)
        .select_related('freelancer', 'category')
    )

    # 2. THE AI SEMANTIC SEARCH BLOCK
    search_query = request.GET.get('q', '').strip()
    
    if search_query:
        try:
            # 1. Embed the user's "vibe" search
            search_vector_response = genai.embed_content(
                model="models/gemini-embedding-2",
                content=search_query,
                task_type="retrieval_query",
                output_dimensionality=768 # Match the database size
            )
            search_vector = search_vector_response['embedding']
            
            # 2. Mathematical Matchmaking
            qs = qs.annotate(
                distance=L2Distance('embedding', search_vector)
            ).order_by('distance')
            
        except Exception as e:
            print(f"🚨 Search AI failed: {e}")
            # Fallback to standard exact-text search if the API is sleepy
            qs = qs.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query)
            ).order_by('-created_at')
    else:
        # If they didn't search for anything, just show newest first
        qs = qs.order_by('-created_at')

    # 3. STANDARD FILTERS (Category & Price)
    category_slug  = request.GET.get('category', '').strip()
    active_category = None
    if category_slug:
        active_category = Category.objects.filter(slug=category_slug).first()
        if active_category:
            qs = qs.filter(category=active_category)

    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    try:
        if min_price:
            qs = qs.filter(price__gte=min_price)
    except (ValueError, TypeError):
        min_price = ''
    try:
        if max_price:
            qs = qs.filter(price__lte=max_price)
    except (ValueError, TypeError):
        max_price = ''
    
    # 4. PAGINATION
    paginator    = Paginator(qs, 9)
    service_list = paginator.get_page(request.GET.get('page'))

    return render(request, 'core/marketplace.html', {
        'services':        service_list,
        'service_list':    service_list,
        'search_query':    search_query,
        'all_categories':  Category.objects.all(),
        'active_category': active_category,
        'min_price':       min_price,
        'max_price':       max_price,
    })


# ---------------------------------------------------------------------------
# Public: Service detail
# ---------------------------------------------------------------------------


def service_detail(request, pk):
    # 1. select_related grabs the user and category in the SAME query (Super fast)
    # 2. We explicitly check is_active=True so hidden gigs return a 404
    service = get_object_or_404(
        Service.objects.select_related('freelancer', 'category'), 
        pk=pk, 
        is_active=True
    )
    
    # Grab all reviews this freelancer has ever received, newest first
    reviews = service.freelancer.reviews_received.select_related('reviewer').order_by('-created_at')
    
    # --- THE AI RECOMMENDATION ENGINE ---
    similar_gigs = []
    
    # Make sure this gig actually has an AI brain before we do math on it
    if service.embedding is not None:
        similar_gigs = (
            Service.objects
            .filter(is_active=True)
            .select_related('freelancer') # Keep it fast so we don't query the DB in the template
            .exclude(pk=service.pk)       # Crucial: Don't recommend the exact same gig!
            .annotate(distance=L2Distance('embedding', service.embedding))
            .order_by('distance')[:3]     # Get the top 3 closest matches
        )
    # ------------------------------------
    
    context = {
        'service': service,
        'reviews': reviews,
        'similar_gigs': similar_gigs, # Added the new AI gigs to your context
    }
    
    return render(request, 'core/service_detail.html', context)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def register(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            # 1. Save the user, but lock the account (is_active = False)
            user = form.save(commit=False)
            user.is_active = False  
            user.save()
            
            # 2. Generate and save the 6-digit OTP
            otp = OTP.objects.create(
                user=user,
                code=OTP.generate_code()
            )
            
            # 3. Send the OTP (this will print to your terminal right now)
            send_otp_email(user, otp.code)
            
            # 4. Redirect them to the new Bouncer page, NOT the marketplace
            messages.success(request, 'Registration successful! Please check your university email for the OTP code (check the spam folder just in case).')
            return redirect('core:verify_otp', user_id=user.id)
            
    else:
        form = StudentRegistrationForm()
        
    return render(request, 'core/register.html', {'form': form})

def verify_otp(request, user_id):
    # This must be named EXACTLY verify_otp to match your urls.py
    user = get_object_or_404(CustomUser, id=user_id, is_active=False)
    
    if request.method == 'POST':
        entered_code = request.POST.get('otp_code')
        
        try:
            otp = OTP.objects.get(user=user, code=entered_code)
            if not otp.is_expired():
                user.is_active = True
                user.save()
                otp.delete() 
                messages.success(request, 'Account verified! You can now log in.')
                return redirect('core:login')
            else:
                messages.error(request, 'OTP has expired.')
                otp.delete() 
        except OTP.DoesNotExist:
            messages.error(request, 'Invalid OTP code.')
    
    return render(request, 'core/verify_otp.html', {'user': user})


# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Wallet — dedicated page for balances + funding
# ---------------------------------------------------------------------------

@login_required
@never_cache
def wallet_view(request):
    wallet = _get_wallet(request.user)

    total_spent = (
        Order.objects
        .filter(client=request.user, status='completed')
        .aggregate(t=Sum('price'))['t'] or Decimal('0.00')
    )
    total_earned = (
        Order.objects
        .filter(freelancer=request.user, status='completed')
        .aggregate(t=Sum('price'))['t'] or Decimal('0.00')
    )

    # Recent transactions for the activity feed (last 10 completed/cancelled)
    recent = (
        Order.objects
        .filter(
            Q(client=request.user) | Q(freelancer=request.user),
            status__in=['completed', 'cancelled'],
        )
        .select_related('service', 'client', 'freelancer')
        .order_by('-updated_at')[:10]
    )

    return render(request, 'core/wallet.html', {
        'wallet':       wallet,
        'total_spent':  total_spent,
        'total_earned': total_earned,
        'recent':       recent,
        'PAYSTACK_PUBLIC_KEY': settings.PAYSTACK_PUBLIC_KEY,
    })


# ---------------------------------------------------------------------------
# My Orders — buyer view
# ---------------------------------------------------------------------------

@login_required
@never_cache
def my_orders(request):
    active_orders = (
        Order.objects
        .filter(client=request.user, status__in=['pending', 'in_progress', 'pending_acceptance'])
        .select_related('service', 'freelancer')
        .order_by('-created_at')
    )
    past_orders = (
        Order.objects
        .filter(client=request.user, status__in=['completed', 'cancelled'])
        .select_related('service', 'freelancer')
        .order_by('-updated_at')
    )
    return render(request, 'core/my_orders.html', {
        'active_orders': active_orders,
        'past_orders':   past_orders,
    })


# ---------------------------------------------------------------------------
# Manage Gigs — seller: gig listings
# ---------------------------------------------------------------------------

@login_required
@never_cache
def manage_gigs(request):
    my_services = (
        Service.objects
        .filter(freelancer=request.user)
        .select_related('category')
        .order_by('-created_at')
    )
    return render(request, 'core/manage_gigs.html', {'my_services': my_services})


# ---------------------------------------------------------------------------
# Manage Sales — seller: incoming orders
# ---------------------------------------------------------------------------

@login_required
@never_cache
def manage_sales(request):
    active_sales = (
        Order.objects
        .filter(freelancer=request.user, status__in=['pending', 'in_progress', 'pending_acceptance'])
        .select_related('service', 'client')
        .order_by('-created_at')
    )
    past_sales = (
        Order.objects
        .filter(freelancer=request.user, status__in=['completed', 'cancelled'])
        .select_related('service', 'client')
        .order_by('-updated_at')
    )
    return render(request, 'core/manage_sales.html', {
        'active_sales': active_sales,
        'past_sales':   past_sales,
    })


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

@login_required
@never_cache
def checkout(request, pk):
    service = get_object_or_404(Service, pk=pk)

    if request.user == service.freelancer:
        messages.error(request, "You can't purchase your own service.")
        return redirect('core:service_detail', pk=pk)

    wallet = _get_wallet(request.user)

    if request.method == 'POST':
        if wallet.available_balance < service.price:
            messages.error(
                request,
                f"Insufficient funds. Your balance is ₦{wallet.available_balance:,.2f} "
                f"but this service costs ₦{service.price:,.2f}. "
                "Please fund your wallet first."
            )
            return redirect('core:wallet')

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            if wallet.available_balance < service.price:
                messages.error(request, "Insufficient funds.")
                return redirect('core:wallet')

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
        'service':    service,
        'wallet':     wallet,
        'can_afford': wallet.available_balance >= service.price,
    })


# ---------------------------------------------------------------------------
# Order detail
# ---------------------------------------------------------------------------

@login_required
@never_cache
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)

    # 1. PERMISSION CHECK
    if request.user != order.client and request.user != order.freelancer:
        messages.error(request, "You don't have permission to view this order.")
        return redirect('core:marketplace')

    # Initialize the form up here!
    msg_form = MessageForm()

    if request.method == 'POST':
        # 2. CHAT LOGIC
        if 'text' in request.POST:
            msg_form = MessageForm(request.POST)
            if msg_form.is_valid():
                msg = msg_form.save(commit=False)
                msg.order  = order
                msg.sender = request.user
                msg.save()
                order.messages.exclude(sender=request.user).update(is_read=True)
                # ONLY redirect if it was successful!
                return redirect('core:order_detail', pk=pk) 
            
            # If it's INVALID, it will skip the redirect and fall to the bottom of the view!

        else:
            # 3. ACTION ENGINE (Accept, Cancel, Complete)
            action = request.POST.get('action')
            print(f"DEBUG: POST data: {dict(request.POST)}, Action: {action}, Order Status: {order.status}")

            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=pk)

                # --- FREELANCER ACTIONS ---
                if request.user == order.freelancer:
                    if action == 'accept' and order.status == 'pending':
                        order.status = 'in_progress'
                        order.save()
                        messages.success(request, "You've accepted the order. Get to work!")

                    elif action == 'cancel' and order.status in ('pending', 'in_progress'):
                        if order.is_funds_in_escrow:
                            bw = Wallet.objects.select_for_update().get(user=order.client)
                            bw.available_balance += order.escrow_amount
                            bw.escrow_balance    -= order.escrow_amount
                            bw.save()
                            order.escrow_amount      = 0
                            order.is_funds_in_escrow = False
                        
                        order.status = 'cancelled'
                        order.save()
                        
                        Notification.objects.create(
                            recipient=order.client,
                            message=f"Order #{order.id} was cancelled by the freelancer. You have been refunded.",
                            link=f"/orders/{order.id}/"
                        )
                        messages.warning(request, "Order cancelled. The buyer has been refunded.")

                # --- CLIENT ACTIONS ---
                elif request.user == order.client:
                    if action == 'complete' and order.status == 'pending_acceptance':
                        if order.is_funds_in_escrow:
                            bw = Wallet.objects.select_for_update().get(user=order.client)
                            fw = Wallet.objects.select_for_update().get(user=order.freelancer)
                            bw.escrow_balance        -= order.escrow_amount
                            fw.available_balance     += order.escrow_amount
                            bw.save()
                            fw.save()
                            order.escrow_amount      = 0
                            order.is_funds_in_escrow = False
                            
                        order.status = 'completed'
                        order.save()
                        messages.success(
                            request,
                            f"Delivery accepted! ₦{order.price:,.2f} released to {order.freelancer.username}."
                        )
                    
                    elif action == 'cancel' and order.status == 'pending': 
                        if order.is_funds_in_escrow:
                            bw = Wallet.objects.select_for_update().get(user=order.client)
                            bw.available_balance += order.escrow_amount
                            bw.escrow_balance    -= order.escrow_amount
                            bw.save()
                            order.escrow_amount      = 0
                            order.is_funds_in_escrow = False
                        
                        order.status = 'cancelled'
                        order.save()
                        
                        Notification.objects.create(
                            recipient=order.freelancer,
                            message=f"Order #{order.id} was cancelled by the buyer.",
                            link=f"/orders/{order.id}/" 
                        )
                        messages.warning(request, "Order cancelled. Your funds have been securely refunded.")
                    
                    elif action == 'cancel' and order.status in ('in_progress', 'pending_acceptance'):
                        messages.error(request, "You cannot cancel an order that is already in progress or delivered. Please message the freelancer.")

            # Redirect after an action is taken
            return redirect('core:order_detail', pk=pk)

    # 4. LOAD MESSAGES FOR GET REQUEST (Or if the form failed!)
    thread = order.messages.select_related('sender').all()
    order.messages.exclude(sender=request.user).update(is_read=True)

    return render(request, 'core/order_detail.html', {
        'order':    order,
        'thread':   thread,
        'msg_form': msg_form, 
    })


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

@login_required
@never_cache
def deliver_order(request, pk):
    order = get_object_or_404(Order, pk=pk)

    if request.user != order.freelancer:
        messages.error(request, "Only the assigned freelancer can submit a delivery.")
        return redirect('core:order_detail', pk=pk)

    if order.status != 'in_progress':
        messages.error(request, "This order is not currently in progress.")
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
                f"Delivery submitted! {order.client.username} will review your work and release payment."
            )
            return redirect('core:order_detail', pk=pk)
    else:
        form = DeliveryForm(instance=order)

    return render(request, 'core/deliver_order.html', {'order': order, 'form': form})


# ---------------------------------------------------------------------------
# Accept order (freelancer shortcut)
# ---------------------------------------------------------------------------

@login_required
@never_cache
def accept_order(request, pk):
    order = get_object_or_404(Order, pk=pk, freelancer=request.user, status='pending')
    if request.method == 'POST':
        order.status = 'in_progress'
        order.save()
        Notification.objects.create(
            recipient=order.client,
            message=f"{request.user.username} has started working on your order!",
            link=f"/orders/{order.pk}/"
        )
        messages.success(request, "Job accepted! You can now start working.")
    return redirect('core:order_detail', pk=pk)


# ---------------------------------------------------------------------------
# Create / Edit / Delete service
# ---------------------------------------------------------------------------

@login_required
@never_cache
def create_service(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save(commit=False)
            service.freelancer = request.user
            service.save()
            messages.success(request, "Your gig has been posted!")
            return redirect('core:manage_gigs')     # ← action-oriented redirect
    else:
        form = ServiceForm()
    return render(request, 'core/create_service.html', {'form': form})


@login_required
@never_cache
def edit_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.user != service.freelancer:
        messages.error(request, "You don't have permission to edit this gig.")
        return redirect('core:service_detail', pk=pk)

    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, "Gig updated.")
            return redirect('core:service_detail', pk=pk)
    else:
        form = ServiceForm(instance=service)

    return render(request, 'core/edit_service.html', {'form': form, 'service': service})


@login_required
@never_cache
def delete_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.user != service.freelancer:
        messages.error(request, "You don't have permission to delete this gig.")
        return redirect('core:service_detail', pk=pk)

    if request.method == 'POST':
        active = service.orders.filter(
            status__in=['pending', 'in_progress', 'pending_acceptance']
        ).count()
        if active:
            messages.error(
                request,
                f"This gig has {active} active order(s) — wait for them to resolve first."
            )
            return redirect('core:service_detail', pk=pk)
        title = service.title
        service.delete()
        messages.success(request, f'"{title}" deleted.')
        return redirect('core:manage_gigs')          # ← action-oriented redirect

    active_order_count = service.orders.filter(
        status__in=['pending', 'in_progress', 'pending_acceptance']
    ).count()
    return render(request, 'core/delete_service.html', {
        'service':            service,
        'active_order_count': active_order_count,
    })


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def public_profile(request, username):
    profile_user    = get_object_or_404(CustomUser, username=username)
    active_services = Service.objects.filter(freelancer=profile_user, is_active=True).order_by('-created_at')
    reviews         = Review.objects.filter(reviewee=profile_user).select_related('reviewer', 'order__service').order_by('-created_at')

    reviewable_orders = []
    if request.user.is_authenticated and request.user != profile_user:
        reviewable_orders = Order.objects.filter(
            client=request.user,
            freelancer=profile_user,
            status='completed',
        ).exclude(review__isnull=False)

    return render(request, 'core/profile.html', {
        'profile_user':      profile_user,
        'active_services':   active_services,
        'reviews':           reviews,
        'reviewable_orders': reviewable_orders,
    })


@login_required
@never_cache
def edit_profile(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect('core:public_profile', username=request.user.username)
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, 'core/edit_profile.html', {'form': form})


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

@login_required
@never_cache
def leave_review(request, order_id):
    order = get_object_or_404(Order, pk=order_id)

    if request.user != order.client:
        messages.error(request, "Only the buyer can leave a review.")
        return redirect('core:order_detail', pk=order_id)
    if order.status != 'completed':
        messages.error(request, "You can only review a completed order.")
        return redirect('core:order_detail', pk=order_id)
    if hasattr(order, 'review'):
        messages.info(request, "You've already reviewed this order.")
        return redirect('core:public_profile', username=order.freelancer.username)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.order    = order
            review.reviewer = request.user
            review.reviewee = order.freelancer
            review.save()
            messages.success(request, f"Review submitted for {order.freelancer.username}.")
            return redirect('core:public_profile', username=order.freelancer.username)
    else:
        form = ReviewForm()

    return render(request, 'core/leave_review.html', {'form': form, 'order': order})


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

@login_required
@never_cache
def inbox(request):
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

    unread_per = {
        t.pk: t.messages.filter(is_read=False).exclude(sender=request.user).count()
        for t in threads
    }

    thread_data = [
        {
            'order':  t,
            'unread': unread_per.get(t.pk, 0),
            'other':  t.freelancer if request.user == t.client else t.client,
        }
        for t in threads
    ]
    return render(request, 'core/inbox.html', {'thread_data': thread_data})


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@login_required
def mark_notifications_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('core:home')          # ← no longer dashboard


# ---------------------------------------------------------------------------
# Paystack verification
# ---------------------------------------------------------------------------

@require_POST
@login_required
@never_cache
def verify_paystack_payment(request):
    try:
        body      = json.loads(request.body)
        reference = body.get('reference', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid request body.'}, status=400)

    if not reference:
        return JsonResponse({'status': 'error', 'message': 'No reference provided.'}, status=400)

    try:
        resp = requests.get(
            f'https://api.paystack.co/transaction/verify/{reference}',
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return JsonResponse({'status': 'error', 'message': f'Paystack unreachable: {e}'}, status=503)

    tx = data.get('data', {})
    if not data.get('status') or tx.get('status') != 'success':
        return JsonResponse({'status': 'error', 'message': 'Payment was not successful.'}, status=400)
    if tx.get('currency') != 'NGN':
        return JsonResponse({'status': 'error', 'message': 'Invalid currency.'}, status=400)

    amount_naira = Decimal(str(tx.get('amount', 0))) / Decimal('100')

    try:
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            wallet.available_balance += amount_naira
            wallet.save(update_fields=['available_balance'])
    except Wallet.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Wallet not found.'}, status=404)

    return JsonResponse({
        'status':      'success',
        'message':     f'₦{amount_naira:,.2f} added to your wallet.',
        'new_balance': float(wallet.available_balance),
    })

@staff_member_required(login_url='core:login')
def admin_dashboard(request):
    """
    Custom staff-only admin dashboard. Completely separate from
    Django's built-in /admin/ site.

    Surfaces platform-wide metrics and a dispute resolution panel
    for all orders where funds are currently locked in escrow.
    """
    # ── Platform metrics ──────────────────────────────────────
    total_users = CustomUser.objects.count()

    total_active_gigs = Service.objects.filter(is_active=True).count()

    total_escrow = (
        Wallet.objects
        .aggregate(total=Sum('escrow_balance'))['total']
        or Decimal('0.00')
    )

    total_available = (
        Wallet.objects
        .aggregate(total=Sum('available_balance'))['total']
        or Decimal('0.00')
    )

    total_orders     = Order.objects.count()
    completed_orders = Order.objects.filter(status='completed').count()
    cancelled_orders = Order.objects.filter(status='cancelled').count()

    # ── Orders with funds locked in escrow (dispute candidates) ──
    # Any order with is_funds_in_escrow=True can be manually resolved.
    # Sorted by age (oldest first) so staff see the longest-waiting first.
    escrow_orders = (
        Order.objects
        .filter(is_funds_in_escrow=True)
        .select_related('service', 'client', 'client__wallet',
                        'freelancer', 'freelancer__wallet')
        .order_by('created_at')
    )

    # ── Recent user signups ──────────────────────────────────
    recent_users = (
        CustomUser.objects
        .order_by('-date_joined')[:10]
    )

    # ── Top services by order count ──────────────────────────
    top_services = (
        Service.objects
        .filter(is_active=True)
        .annotate(order_count=Count('orders'))
        .order_by('-order_count')[:5]
    )

    return render(request, 'core/admin_dashboard.html', {
        'total_users':       total_users,
        'total_active_gigs': total_active_gigs,
        'total_escrow':      total_escrow,
        'total_available':   total_available,
        'total_orders':      total_orders,
        'completed_orders':  completed_orders,
        'cancelled_orders':  cancelled_orders,
        'escrow_orders':     escrow_orders,
        'recent_users':      recent_users,
        'top_services':      top_services,
    })


# ─────────────────────────────────────────────────────────────
# Dispute action: refund the client
# ─────────────────────────────────────────────────────────────

@staff_member_required(login_url='core:login')
@require_POST
def refund_client(request, order_id):
    """
    Staff action: cancel an order and refund the buyer.

    Moves escrow_amount from client.wallet.escrow_balance
    back to client.wallet.available_balance, then marks
    the order as 'cancelled' and clears the escrow fields.

    Guards:
      - is_funds_in_escrow must be True (prevents double-refund)
      - select_for_update() prevents race conditions
    """
    order = get_object_or_404(Order, pk=order_id)

    if not order.is_funds_in_escrow:
        messages.warning(
            request,
            f"Order #{order.id}: no funds in escrow — already resolved."
        )
        return redirect('core:admin_dashboard')

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)

        # Double-check inside the lock
        if not order.is_funds_in_escrow:
            messages.warning(
                request,
                f"Order #{order.id}: funds were already released by another action."
            )
            return redirect('core:admin_dashboard')

        client_wallet = (
            Wallet.objects
            .select_for_update()
            .get(user=order.client)
        )

        # Move escrow → client's available balance
        refund_amount = order.escrow_amount
        client_wallet.escrow_balance    -= refund_amount
        client_wallet.available_balance += refund_amount
        client_wallet.save()

        # Clear escrow on the order and mark cancelled
        order.escrow_amount      = Decimal('0.00')
        order.is_funds_in_escrow = False
        order.status             = 'cancelled'
        order.save()

        # Notify both parties
        Notification.objects.create(
            recipient=order.client,
            message=(
                f"[Admin] Your order for '{order.service.title}' was cancelled "
                f"and ₦{refund_amount:,.2f} has been refunded to your wallet."
            ),
            link=f"/orders/{order.pk}/",
        )
        Notification.objects.create(
            recipient=order.freelancer,
            message=(
                f"[Admin] Order #{order.id} for '{order.service.title}' "
                f"was cancelled by platform staff."
            ),
            link=f"/orders/{order.pk}/",
        )

    messages.success(
        request,
        f"Order #{order.id}: ₦{refund_amount:,.2f} refunded to "
        f"{order.client.username}. Order marked cancelled."
    )
    return redirect('core:admin_dashboard')


# ─────────────────────────────────────────────────────────────
# Dispute action: pay the freelancer
# ─────────────────────────────────────────────────────────────

@staff_member_required(login_url='core:login')
@require_POST
def pay_freelancer(request, order_id):
    """
    Staff action: force-complete an order and release payment.

    Moves escrow_amount from client.wallet.escrow_balance
    to freelancer.wallet.available_balance, then marks
    the order as 'completed' and clears the escrow fields.

    Guards:
      - is_funds_in_escrow must be True (prevents double-payment)
      - select_for_update() prevents race conditions
      - Both wallets are locked in a single atomic block
    """
    order = get_object_or_404(Order, pk=order_id)

    if not order.is_funds_in_escrow:
        messages.warning(
            request,
            f"Order #{order.id}: no funds in escrow — already resolved."
        )
        return redirect('core:admin_dashboard')

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)

        # Double-check inside the lock
        if not order.is_funds_in_escrow:
            messages.warning(
                request,
                f"Order #{order.id}: funds were already released by another action."
            )
            return redirect('core:admin_dashboard')

        # Lock both wallets in a consistent order (lower PK first)
        # to prevent deadlocks if two actions run concurrently.
        user_pks = sorted([order.client.pk, order.freelancer.pk])
        wallets  = {
            w.user_id: w
            for w in Wallet.objects
                           .select_for_update()
                           .filter(user_id__in=user_pks)
        }

        client_wallet     = wallets[order.client.pk]
        freelancer_wallet = wallets[order.freelancer.pk]

        payment_amount = order.escrow_amount

        # Move: client escrow → freelancer available
        client_wallet.escrow_balance        -= payment_amount
        freelancer_wallet.available_balance  += payment_amount
        client_wallet.save()
        freelancer_wallet.save()

        # Clear escrow on the order and mark completed
        order.escrow_amount      = Decimal('0.00')
        order.is_funds_in_escrow = False
        order.status             = 'completed'
        order.save()

        # Notify both parties
        Notification.objects.create(
            recipient=order.freelancer,
            message=(
                f"[Admin] Payment of ₦{payment_amount:,.2f} for "
                f"'{order.service.title}' has been released to your wallet."
            ),
            link=f"/orders/{order.pk}/",
        )
        Notification.objects.create(
            recipient=order.client,
            message=(
                f"[Admin] Order #{order.id} for '{order.service.title}' "
                f"has been marked complete by platform staff."
            ),
            link=f"/orders/{order.pk}/",
        )

    messages.success(
        request,
        f"Order #{order.id}: ₦{payment_amount:,.2f} paid to "
        f"{order.freelancer.username}. Order marked complete."
    )
    return redirect('core:admin_dashboard')

