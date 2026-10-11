from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Notification(models.Model):
    """
    Official statutory notices and lifecycle alerts sent to users.
    """
    class NotificationType(models.TextChoices):
        EXPIRY_WARNING = 'EXPIRY', _('Re-verification Expiry Notice')
        INSPECTION_SCHEDULED = 'INSPECTION', _('Official Inspection Scheduled')
        CERTIFICATE_ISSUED = 'CERTIFICATE', _('Digital Certificate Issued')
        REJECTION_NOTICE = 'REJECTION', _('Verification Non-Compliance Notice')
        GENERAL = 'GENERAL', _('Regulatory Advisory')

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Recipient User')
    )
    title = models.CharField(
        max_length=255,
        verbose_name=_('Notice Subject')
    )
    message = models.TextField(
        verbose_name=_('Official Notice Content')
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
        verbose_name=_('Notice Type')
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name=_('Read Status')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Official Notification')
        verbose_name_plural = _('Official Notifications')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notification_type_display()}: {self.title} -> {self.recipient.username}"
