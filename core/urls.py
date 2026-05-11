# core/urls.py

from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from django.views.generic.base import RedirectView
from . import views

app_name = 'core'

urlpatterns = [
    # --- Public ---
    path('', views.marketplace, name='home'),
    path('marketplace/', RedirectView.as_view(pattern_name='core:home', permanent=False)),
    path('services/<int:pk>/', views.service_detail, name='service_detail'),
    path('services/<int:pk>/checkout/', views.checkout, name='checkout'),

    

    # --- Buyer ---
    path('orders/my/', views.my_orders, name='my_orders'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/deliver/', views.deliver_order, name='deliver_order'),
    path('orders/<int:pk>/accept/', views.accept_order, name='accept_order'),
    path('orders/<int:order_id>/review/', views.leave_review, name='leave_review'),

    # --- Seller ---
    path('gigs/', views.manage_gigs, name='manage_gigs'),
    path('gigs/new/', views.create_service, name='create_service'),
    path('gigs/<int:pk>/edit/', views.edit_service, name='edit_service'),
    path('gigs/<int:pk>/delete/', views.delete_service, name='delete_service'),
    path('sales/', views.manage_sales, name='manage_sales'),

    # --- Wallet ---
    path('wallet/', views.wallet_view, name='wallet'),
    path('wallet/verify/', views.verify_paystack_payment, name='verify_payment'),

    # --- Profiles ---
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/<str:username>/', views.public_profile, name='public_profile'),

    # --- Inbox ---
    path('inbox/', views.inbox, name='inbox'),

    # --- Notifications ---
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),

    # --- Auth ---
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='core/password_reset.html',
        email_template_name='core/password_reset_email.html',
        subject_template_name='core/password_reset_subject.txt',
        success_url=reverse_lazy('core:password_reset_done')
    ), name='password_reset'),

    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='core/password_reset_done.html'
    ), name='password_reset_done'),

    path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='core/password_reset_confirm.html',
        success_url=reverse_lazy('core:password_reset_complete')
    ), name='password_reset_confirm'),

    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='core/password_reset_complete.html'
    ), name='password_reset_complete'),
    path('verify-otp/<int:user_id>/', views.verify_otp, name='verify_otp'),

    # core/urls.py  ── add these three paths inside urlpatterns ──

    # --- Staff Admin Panel ---
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/refund/<int:order_id>/', views.refund_client, name='refund_client'),
    path('admin-panel/pay/<int:order_id>/', views.pay_freelancer, name='pay_freelancer'),
]