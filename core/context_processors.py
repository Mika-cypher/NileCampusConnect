# core/context_processors.py

from .models import Notification, Message


def notifications(request):
    """
    Injects notification data into every template context.

    Returns empty defaults for anonymous users so templates don't
    need to guard against missing variables with {% if request.user.is_authenticated %}.

    Variables available in every template:
        unread_notifications  — QuerySet, up to 5 most recent unread Notifications
        unread_notif_count    — int, total unread notification count
        unread_message_count  — int, unread messages across all the user's orders
                                (powers the sidebar Inbox badge)
    """
    if not request.user.is_authenticated:
        return {
            'unread_notifications':  [],
            'unread_notif_count':    0,
            'unread_message_count':  0,
        }

    # Notifications — cap at 5 for the dropdown, but count all unread
    unread_qs = (
        Notification.objects
        .filter(recipient=request.user, is_read=False)
        .order_by('-created_at')
    )
    unread_notif_count   = unread_qs.count()
    unread_notifications = unread_qs[:5]   # slicing evaluates the queryset — intentional

    # Unread message count — messages sent to the user in any of their orders
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

    return {
        'unread_notifications':  unread_notifications,
        'unread_notif_count':    unread_notif_count,
        'unread_message_count':  unread_message_count,
    }