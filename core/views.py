from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.db.models import Q
from .models import Order, Service
from .forms import StudentRegistrationForm, ServiceForm


@login_required
def dashboard(request):
    # 1. Fetch Lists for the "Buying" side (Client)
    active_orders = Order.objects.filter(
        client=request.user, 
        status__in=['pending', 'in_progress']
    ).order_by('-created_at')
    
    completed_orders = Order.objects.filter(
        client=request.user, 
        status__in=['completed', 'cancelled']
    ).order_by('-updated_at')

    # 2. Fetch Lists for the "Selling" side (Freelancer)
    incoming_jobs = Order.objects.filter(
        freelancer=request.user, 
        status__in=['pending', 'in_progress']
    ).order_by('-created_at')
    
    completed_jobs = Order.objects.filter(
        freelancer=request.user, 
        status__in=['completed', 'cancelled']
    ).order_by('-updated_at')

    # 3. Your existing services logic
    services = Service.objects.filter(freelancer=request.user)

    context = {
        'active_orders': active_orders,
        'completed_orders': completed_orders, # NEW
        'incoming_jobs': incoming_jobs,
        'completed_jobs': completed_jobs,     # NEW
        'services': services
    }
    return render(request, 'core/dashboard.html', context)


def register(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST) # Use your actual form class here
        if form.is_valid():
            user = form.save()
            
            # --- THE FIX IS HERE ---
            # We explicitly tell Django to use the standard ModelBackend
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            return redirect('core:dashboard')
    else:
        form = StudentRegistrationForm()
    return render(request, 'core/register.html', {'form': form})


@login_required
def create_service(request):
    """
    View for creating a new service/gig.
    Requires user to be logged in.
    On POST: save the form and set freelancer to current user.
    On GET: render the service creation form.
    """
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            service.freelancer = request.user
            service.save()
            return redirect('core:dashboard')
    else:
        form = ServiceForm()
    
    return render(request, 'core/create_service.html', {'form': form})


def marketplace(request):
    """
    Marketplace view displaying all available services/gigs.
    Supports search functionality via ?q= parameter.
    """
    services = Service.objects.filter(is_active=True).select_related('freelancer').order_by('-created_at')
    
    # Handle search parameter
    search_query = request.GET.get('q', '')
    if search_query:
        services = services.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )
    
    context = {
        'services': services,
        'search_query': search_query,
    }
    
    return render(request, 'core/marketplace.html', context)

from django.shortcuts import render, get_object_or_404
from .models import Service

def service_detail(request, pk):
    service = get_object_or_404(Service, pk=pk)
    return render(request, 'core/service_detail.html', {'service': service})

@login_required
def checkout(request, pk):
    service = get_object_or_404(Service, pk=pk)

    # Prevent buying your own gig
    if request.user == service.freelancer:
        return redirect('core:service_detail', pk=pk)

    if request.method == 'POST':
        # 1. Create the Order
        order = Order.objects.create(
            client=request.user,
            freelancer=service.freelancer,
            service=service,
            status='in_progress',  # We assume payment worked instantly for now
            price=service.price,
            escrow_amount=service.price, # Simulate money moving to escrow
            is_funds_in_escrow=True
        )
        
        # 2. Redirect to Dashboard (Success!)
        return redirect('core:dashboard')

    return render(request, 'core/checkout.html', {'service': service})

    # --- PASTE THIS AT THE BOTTOM OF core/views.py ---

@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)

    # Security: Only allow the Buyer or Seller to see this page
    if request.user != order.client and request.user != order.freelancer:
        return redirect('core:dashboard')

    # Handle Status Updates (POST requests)
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Logic for Freelancer
        if request.user == order.freelancer:
            if action == 'accept':
                order.status = 'in_progress'
            elif action == 'cancel':
                order.status = 'cancelled'
        
        # Logic for Client
        elif request.user == order.client:
            if action == 'complete':
                order.status = 'completed'
                # TODO: We will add the money transfer logic here later
        
        order.save()
        return redirect('core:order_detail', pk=pk)

    return render(request, 'core/order_detail.html', {'order': order})