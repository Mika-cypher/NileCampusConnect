from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'core'

urlpatterns = [
    # --- Main Pages ---
    path('dashboard/', views.dashboard, name='dashboard'),
    path('marketplace/', views.marketplace, name='marketplace'),
    
    # --- Service & Order Pages ---
    path('services/new/', views.create_service, name='create_service'),
    path('services/<int:pk>/', views.service_detail, name='service_detail'),
    path('services/<int:pk>/checkout/', views.checkout, name='checkout'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),

    # --- Auth Pages (Login/Logout/Register) ---
    path('register/', views.register, name='register'),
    
    # Added Login Path (Points to a template we will ensure exists)
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),

    # Logout Path (Redirects to the 'login' page name defined above)
    path('logout/', auth_views.LogoutView.as_view(next_page='core:login'), name='logout'),
]