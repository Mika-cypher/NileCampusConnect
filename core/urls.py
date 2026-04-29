# core/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'core'

urlpatterns = [
    # --- Landing ---
    path('', views.home, name='home'),

    # --- Main App ---
    path('dashboard/', views.dashboard, name='dashboard'),
    path('marketplace/', views.marketplace, name='marketplace'),
    path('inbox/', views.inbox, name='inbox'),

    # --- Services ---
    path('services/new/', views.create_service, name='create_service'),
    path('services/<int:pk>/', views.service_detail, name='service_detail'),
    path('services/<int:pk>/checkout/', views.checkout, name='checkout'),
    path('services/<int:pk>/edit/', views.edit_service, name='edit_service'),
    path('services/<int:pk>/delete/', views.delete_service, name='delete_service'),

    # --- Orders ---
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/deliver/', views.deliver_order, name='deliver_order'),
    path('orders/<int:order_id>/review/', views.leave_review, name='leave_review'),

    # --- Profiles ---
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/<str:username>/', views.public_profile, name='public_profile'),

    # --- Notifications ---
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),

    # --- Auth ---
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='core:login'), name='logout'),
    path('orders/<int:pk>/accept/', views.accept_order, name='accept_order'),
    path('verify-payment/', views.verify_paystack_payment, name='verify_payment'),
]