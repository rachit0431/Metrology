from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, InstrumentOwnerProfile, LMOProfile, GATCProfile

@receiver(post_save, sender=User)
def ensure_profile_exists(sender, instance, created, **kwargs):
    """
    Ensure safety fallback so users always have their matching profile
    if created directly through management commands or shell without a form/inline.
    """
    if not created or getattr(instance, '_skip_default_profile_signal', False):
        return

    if instance.role == User.Role.INSTRUMENT_OWNER:
        user_pk = instance.pk

        def _create_fallback_owner_profile():
            if not InstrumentOwnerProfile.objects.filter(user_id=user_pk).exists():
                user_obj = User.objects.filter(pk=user_pk).first()
                if user_obj and user_obj.role == User.Role.INSTRUMENT_OWNER:
                    InstrumentOwnerProfile.objects.get_or_create(
                        user=user_obj,
                        defaults={
                            'business_name': f"{user_obj.username.title()} Enterprise",
                            'trade_license_number': f"TL-{user_obj.id:04d}",
                            'contact_person': user_obj.get_full_name() or user_obj.username,
                            'phone': user_obj.phone or 'Not Provided',
                            'email': user_obj.email or f"{user_obj.username}@example.com",
                            'address': 'Pending official profile update',
                            'state': 'Pending',
                            'district': 'Pending',
                            'pincode': '000000',
                        }
                    )

        transaction.on_commit(_create_fallback_owner_profile)
