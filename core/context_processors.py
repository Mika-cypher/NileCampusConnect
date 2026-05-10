# core/context_processors.py

from .models import Notification, Message, Category, Service, Order


def notifications(request):
    """
    Injects notification data, unread message count, all categories,
    and user role flags into every template context.
    """
    # ── Always-available data (works for unauthenticated users too) ──
    all_categories = Category.objects.all().order_by('name')

    if not request.user.is_authenticated:
        return {
            'unread_notifications':  [],
            'unread_notif_count':    0,
            'unread_message_count':  0,
            'all_categories':        all_categories,
            'user_has_gigs':         False,
            'user_has_active_orders': False,
        }

    # ── Notifications ────────────────────────────────────────────────
    unread_qs = (
        Notification.objects
        .filter(recipient=request.user, is_read=False)
        .order_by('-created_at')
    )
    unread_notif_count   = unread_qs.count()
    unread_notifications = unread_qs[:5]

    # ── Unread messages ──────────────────────────────────────────────
    from django.db.models import Q
    unread_message_count = (
        Message.objects
        .filter(
            Q(order__client=request.user) | Q(order__freelancer=request.user),
            is_read=False,
        )
        .exclude(sender=request.user)
        .count()
    )

    # ── Role flags — drive conditional nav links ─────────────────────
    # Cached as simple booleans — one query each, never expensive
    user_has_gigs = Service.objects.filter(
        freelancer=request.user, is_active=True
    ).exists()

    user_has_active_orders = Order.objects.filter(
        client=request.user,
        status__in=['pending', 'in_progress', 'pending_acceptance']
    ).exists()

    return {
        'unread_notifications':    unread_notifications,
        'unread_notif_count':      unread_notif_count,
        'unread_message_count':    unread_message_count,
        'all_categories':          all_categories,
        'user_has_gigs':           user_has_gigs,
        'user_has_active_orders':  user_has_active_orders,
    }