# NileCampusConnect - AI Coding Agent Instructions

## Project Overview
NileCampusConnect is a Django-based marketplace platform exclusively for Nile University of Nigeria students. It enables students to offer freelance services (gigs) and purchase services within a verified campus community, featuring an escrow payment system.

## Architecture & Key Components

### Core Models (`core/models.py`)
- **CustomUser**: Extends Django's AbstractUser with `wallet_balance` field for escrow functionality
- **Service**: Represents freelance gigs with title, price, description, delivery_time, and freelancer relationship
- **Order**: Manages transactions with status workflow: `pending` → `pending_acceptance` → `in_progress` → `completed`/`cancelled`

### Authentication System
- **EmailBackend** (`core/backends.py`): Enables login via email or username
- **StudentRegistrationForm** (`core/forms.py`): Validates emails end with `@nileuniversity.edu.ng`
- Custom user model referenced in `AUTH_USER_MODEL = 'core.CustomUser'`

### URL Structure
- App namespace: `core`
- Key routes: `dashboard/`, `marketplace/`, `services/<pk>/`, `orders/<pk>/`
- Root URL redirects to `/dashboard/`

## Critical Workflows

### Service Creation & Marketplace
```python
# In views.py - create_service view
service = form.save(commit=False)
service.freelancer = request.user
service.save()
```
Services are displayed in marketplace with search via `?q=` parameter.

### Order Management
- **Checkout**: Creates Order with `status='in_progress'`, simulates escrow
- **Order Detail**: Freelancers can `accept`/`cancel`, clients can mark `complete`
- Status updates trigger workflow transitions

### Dashboard Logic
Separates client/freelancer roles:
- `active_orders`: Client's pending/in_progress orders
- `incoming_jobs`: Freelancer's pending/in_progress orders
- `completed_orders`/`completed_jobs`: Historical records

## Development Patterns

### Status Display
Use `order.get_status_display_class()` for Bootstrap badge classes:
```python
status_classes = {
    'pending': 'badge-secondary',
    'pending_acceptance': 'badge-info',
    'in_progress': 'badge-warning',
    'completed': 'badge-success',
    'cancelled': 'badge-danger',
}
```

### Form Validation
Registration form enforces Nile University email domain:
```python
def clean_email(self):
    email = self.cleaned_data.get('email')
    if not email.endswith('@nileuniversity.edu.ng'):
        raise forms.ValidationError('You must have a Nile University email address.')
```

### Frontend Integration
- Bootstrap 5 with custom Nile blue theme (`--nile-blue: #003366`)
- Static files served via `{% load static %}`
- Templates extend `core/base.html` with sidebar navigation

## Database & Deployment

### Migrations
- SQLite for development (`db.sqlite3`)
- PostgreSQL intended for production
- Custom user model requires proper migration handling

### Security Notes
- `DEBUG = True` in development
- Custom authentication backend for email login
- Login required for service creation and order management

## Common Development Tasks

### Setup Environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install django  # Note: requirements.txt missing from repo
python manage.py migrate
python manage.py runserver
```

### Adding Features
- New views typically require: URL pattern, view function, template, and navigation link
- Model changes need migrations: `python manage.py makemigrations`
- Forms extend Django's ModelForm with Bootstrap classes

### Testing Order Flow
1. Register two users with Nile University emails
2. Create service as freelancer
3. Purchase as client (triggers checkout → order creation)
4. Test status updates from both sides

## File Organization Reference
- `core/models.py`: Data models and relationships
- `core/views.py`: Business logic and request handling
- `core/forms.py`: User input validation
- `core/templates/core/`: HTML templates with Bootstrap styling
- `core/static/core/css/`: Custom CSS with Nile branding
- `NileCampusConnect/settings.py`: Django configuration

### Order Management
- **Order Detail**: Freelancers can `accept`/`cancel`, clients can `complete`/`cancel`