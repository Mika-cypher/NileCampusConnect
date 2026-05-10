# core/signals.py

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from .models import CustomUser, Order, Message, Notification
from django.conf import settings
from .models import Service
import google.generativeai as genai

genai.configure(api_key=settings.GEMINI_API_KEY)

# Wallet auto-creation

@receiver(post_save, sender=CustomUser)
def create_wallet_for_new_user(sender, instance, created, **kwargs):
    """Provision a Wallet the moment a new user is registered."""
    if created:
        from .models import Wallet
        Wallet.objects.get_or_create(user=instance)


# ─────────────────────────────────────────────────────────────
# Order status-change notifications
#
# Pattern: pre_save caches the DB-current status onto the instance
# so post_save can compare old vs new without touching the model class.
# Cost: one extra SELECT per Order.save() — acceptable.
# ─────────────────────────────────────────────────────────────

@receiver(pre_save, sender=Order)
def cache_previous_order_status(sender, instance, **kwargs):
    """
    Before saving, read the current status from the DB and stash it
    on the instance as `_previous_status`. New (unsaved) orders get None.
    """
    if instance.pk:
        try:
            instance._previous_status = (
                Order.objects.filter(pk=instance.pk)
                             .values_list('status', flat=True)
                             .get()
            )
        except Order.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Order)
def notify_on_order_status_change(sender, instance, created, **kwargs):
    """
    Fire a Notification to the relevant party whenever an Order's
    status moves to a milestone state.

    Transitions we care about:
      pending        → in_progress        : tell the CLIENT their order was accepted
      in_progress    → pending_acceptance : tell the CLIENT work has been delivered
      pending_accept → completed          : tell the FREELANCER payment was released
    """
    if created:
        return  # nothing to diff on a brand-new order

    old = getattr(instance, '_previous_status', None)
    new = instance.status

    if old == new:
        return  # status didn't change — e.g. only escrow fields updated

    order_url = reverse('core:order_detail', kwargs={'pk': instance.pk})
    service_title = instance.service.title

    # ── Seller accepted → notify buyer ──
    if old == 'pending' and new == 'in_progress':
        Notification.objects.create(
            recipient=instance.client,
            message=(
                f'Your order for "{service_title}" has been accepted. '
                f'{instance.freelancer.username} is now working on it.'
            ),
            link=order_url,
        )

    # ── Seller submitted delivery → notify buyer ──
    elif old == 'in_progress' and new == 'pending_acceptance':
        Notification.objects.create(
            recipient=instance.client,
            message=(
                f'{instance.freelancer.username} has submitted their delivery '
                f'for "{service_title}". Please review and accept.'
            ),
            link=order_url,
        )

    # ── Buyer accepted → notify freelancer ──
    elif old == 'pending_acceptance' and new == 'completed':
        Notification.objects.create(
            recipient=instance.freelancer,
            message=(
                f'Great news! {instance.client.username} accepted your delivery '
                f'for "{service_title}". Payment has been released to your wallet.'
            ),
            link=order_url,
        )

    # ── Order cancelled → notify whichever party didn't cancel ──
    elif new == 'cancelled':
        # Figure out who to notify: if client cancelled, tell freelancer and vice versa
        # We can't know *who* cancelled from the signal alone, so notify both
        # (they'll only see one unread notification each — harmless).
        for recipient in [instance.client, instance.freelancer]:
            Notification.objects.create(
                recipient=recipient,
                message=f'Order for "{service_title}" has been cancelled.',
                link=order_url,
            )


# ─────────────────────────────────────────────────────────────
# New message notifications
# ─────────────────────────────────────────────────────────────

@receiver(post_save, sender=Message)
def notify_on_new_message(sender, instance, created, **kwargs):
    """
    When a new Message is created, notify the other party in the thread.
    We intentionally do NOT notify the sender about their own message.
    """
    if not created:
        return

    order = instance.order
    sender_user = instance.sender

    # The recipient is whoever in the order is NOT the sender
    if sender_user == order.client:
        recipient = order.freelancer
    else:
        recipient = order.client

    order_url = reverse('core:order_detail', kwargs={'pk': order.pk})

    Notification.objects.create(
        recipient=recipient,
        message=(
            f'New message from {sender_user.username} '
            f'on order "{order.service.title}".'
        ),
        link=order_url,
    )

@receiver(post_save, sender=Service)
def generate_service_embedding(sender, instance, created, **kwargs):
    print(f"🚨 DEBUG: Signal just woke up for Gig: {instance.title}")
    print(f"🚨 DEBUG: Embedding value is currently: {repr(instance.embedding)}")
    if instance.embedding is None:
        try:
            text_to_embed = f"Title: {instance.title}. Description: {instance.description}"
            
            # Using the NEW 2026 model
            response = genai.embed_content(
                model="models/gemini-embedding-2", # Updated model
                content=text_to_embed,
                task_type="retrieval_document",
                output_dimensionality=768 # Forces it to stay at 768!
            )
            
            instance.embedding = response['embedding']
            instance.save(update_fields=['embedding'])
            
        except Exception as e:
            print(f"AI Embedding Failed: {e}")