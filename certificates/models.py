import hashlib
import secrets
from datetime import timedelta
import segno
from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from instruments.models import Instrument
from verification.models import VerificationApplication, AuditLog


class VerificationCertificate(models.Model):
    """
    Official digital certificate of verification issued after a successful
    metrological inspection.
    Includes a cryptographically secure verification token, SHA-256 integrity hash,
    QR verification endpoint URL, and immutability protection.
    """
    class Status(models.TextChoices):
        VALID = 'VALID', _('Valid')
        EXPIRED = 'EXPIRED', _('Expired')
        REVOKED = 'REVOKED', _('Revoked')

    certificate_number = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        verbose_name=_('Certificate Number')
    )
    application = models.OneToOneField(
        VerificationApplication,
        on_delete=models.CASCADE,
        related_name='certificate',
        verbose_name=_('Verification Application')
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name='certificates',
        verbose_name=_('Verified Instrument')
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='owned_certificates',
        verbose_name=_('Instrument Owner')
    )
    issuing_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='issued_certificates',
        limit_choices_to={'role': 'LMO'},
        verbose_name=_('Issuing Officer (LMO)')
    )
    issuing_gatc = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='gatc_issued_certificates',
        limit_choices_to={'role': 'GATC'},
        verbose_name=_('Testing / Certifying GATC')
    )
    issue_date = models.DateField(
        default=timezone.localdate,
        verbose_name=_('Date of Issuance')
    )
    valid_until = models.DateField(
        verbose_name=_('Valid Until Date')
    )
    verification_status = models.CharField(
        max_length=20,
        choices=[
            (Status.VALID, _('Valid')),
            (Status.EXPIRED, _('Expired')),
            (Status.REVOKED, _('Revoked')),
        ],
        default=Status.VALID,
        verbose_name=_('Verification Status')
    )
    certificate_hash = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_('Certificate SHA-256 Hash')
    )
    verification_token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        verbose_name=_('Secure Verification Token')
    )
    qr_verification_url = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('QR Verification URL')
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Revoked Timestamp')
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_certificates',
        verbose_name=_('Revoked By (Admin)')
    )
    revocation_reason = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Revocation Reason')
    )
    generated_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Generated Timestamp')
    )

    class Meta:
        verbose_name = _('Verification Certificate')
        verbose_name_plural = _('Verification Certificates')
        ordering = ['-issue_date', '-generated_at']

    def __str__(self):
        return f"Certificate #{self.certificate_number} - {self.instrument.instrument_name}"

    # Backward-compatible aliases
    @property
    def status(self):
        return self.effective_status

    @status.setter
    def status(self, value):
        if value == 'ACTIVE':
            value = self.Status.VALID
        self.verification_status = value

    @property
    def digital_signature_hash(self):
        return self.certificate_hash

    @property
    def created_at(self):
        return self.generated_at

    @property
    def effective_status(self):
        if self.verification_status == self.Status.REVOKED:
            return self.Status.REVOKED
        if self.valid_until and self.valid_until < timezone.localdate():
            return self.Status.EXPIRED
        return self.Status.VALID

    @property
    def is_currently_valid(self):
        return self.effective_status == self.Status.VALID

    @property
    def authorized_verifier_display(self):
        parts = []
        if self.issuing_officer:
            parts.append(f"{self.issuing_officer.display_name} (LMO)")
        if self.issuing_gatc:
            parts.append(f"{self.issuing_gatc.display_name} (GATC)")
        return " / ".join(parts) if parts else "Authorized Legal Metrology Authority"

    def generate_qr_svg(self, absolute_verify_url=None, scale=4):
        """
        Generates an inline SVG QR code pointing to `/verify/<verification_token>/`.
        """
        target_url = absolute_verify_url or self.qr_verification_url or f"/verify/{self.verification_token}/"
        qr = segno.make(target_url, error='M')
        return qr.svg_inline(scale=scale, dark='#0f2942', light='#ffffff', border=2)

    def save(self, *args, **kwargs):
        # Immutability guard: prevent tampering with core issued certificate data
        if self.pk is not None:
            orig = VerificationCertificate.objects.filter(pk=self.pk).first()
            if orig:
                immutable_Pairs = [
                    (orig.certificate_number, self.certificate_number),
                    (orig.instrument_id, self.instrument_id),
                    (orig.application_id, self.application_id),
                    (orig.issue_date, self.issue_date),
                    (orig.valid_until, self.valid_until),
                    (orig.certificate_hash, self.certificate_hash),
                    (orig.verification_token, self.verification_token),
                ]
                if any(a and a != b for a, b in immutable_Pairs):
                    raise PermissionDenied(
                        "Issued digital certificates are immutable. Core certificate particulars "
                        "(number, instrument, dates, hash, and token) cannot be altered."
                    )

        if not self.owner_id and self.instrument_id:
            self.owner = self.instrument.owner

        if not self.verification_token:
            self.verification_token = secrets.token_urlsafe(24)

        if not self.qr_verification_url:
            self.qr_verification_url = f"/verify/{self.verification_token}/"

        if not self.certificate_hash:
            payload = (
                f"{self.instrument_id}:{self.application_id}:{self.issue_date}:"
                f"{self.valid_until}:{self.verification_token}:{secrets.token_hex(8)}"
            )
            self.certificate_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()

        super().save(*args, **kwargs)

        if not self.certificate_number:
            year = self.issue_date.year if self.issue_date else timezone.localdate().year
            self.certificate_number = f"LM-{year}-{self.pk:06d}"
            super().save(update_fields=['certificate_number'])

    @transaction.atomic
    def revoke(self, admin_user, reason):
        """
        Controlled administrative revocation of an issued certificate.
        """
        if not (admin_user.is_superuser or getattr(admin_user, 'role', '') == 'ADMIN'):
            raise PermissionDenied("Only authorized Administrators may revoke a verification certificate.")
        if not reason or not reason.strip():
            raise ValidationError("A formal revocation reason is required.")

        now = timezone.now()
        self.verification_status = self.Status.REVOKED
        self.revoked_at = now
        self.revoked_by = admin_user
        self.revocation_reason = reason.strip()
        VerificationCertificate.objects.filter(pk=self.pk).update(
            verification_status=self.verification_status,
            revoked_at=self.revoked_at,
            revoked_by=self.revoked_by,
            revocation_reason=self.revocation_reason,
        )

        # Reflect revocation on instrument status
        self.instrument.status = Instrument.Status.SUSPENDED
        self.instrument.save(update_fields=['status', 'updated_at'])

        AuditLog.log_event(
            actor=admin_user,
            action=f"Certificate {self.certificate_number} REVOKED by Administration",
            instrument=self.instrument,
            application=self.application,
            previous_status=self.Status.VALID,
            new_status=self.Status.REVOKED,
            remarks=f"Revocation Reason: {self.revocation_reason}",
        )
        return self

    @classmethod
    @transaction.atomic
    def issue_for_application(cls, application, actor=None):
        """
        Generates a digital VerificationCertificate for an approved application,
        updates the application status to CERTIFICATE_ISSUED, and writes an AuditLog entry.
        """
        existing = cls.objects.filter(application=application).first()
        if existing:
            if application.status != VerificationApplication.Status.CERTIFICATE_ISSUED:
                prev = application.status
                application.status = VerificationApplication.Status.CERTIFICATE_ISSUED
                application.save(update_fields=['status', 'updated_at'])
                AuditLog.log_event(
                    actor=actor,
                    action=f"Digital Certificate {existing.certificate_number} linked to application",
                    instrument=application.instrument,
                    application=application,
                    previous_status=prev,
                    new_status=VerificationApplication.Status.CERTIFICATE_ISSUED,
                )
            return existing

        if application.status not in {
            VerificationApplication.Status.PASSED,
            VerificationApplication.Status.CERTIFICATE_ISSUED,
        }:
            raise ValidationError("A certificate can only be generated after the application has PASSED inspection.")

        today = timezone.localdate()
        validity_months = (
            application.instrument.category.standard_verification_validity_months
            if application.instrument.category_id else 12
        )
        valid_until = (
            application.instrument.next_verification_date
            or (today + timedelta(days=validity_months * 30))
        )

        issuing_lmo = application.assigned_officer
        issuing_gatc = application.assigned_gatc
        if actor and getattr(actor, 'role', '') == 'LMO' and not issuing_lmo:
            issuing_lmo = actor
        elif actor and getattr(actor, 'role', '') == 'GATC' and not issuing_gatc:
            issuing_gatc = actor

        cert = cls.objects.create(
            application=application,
            instrument=application.instrument,
            owner=application.instrument.owner,
            issuing_officer=issuing_lmo,
            issuing_gatc=issuing_gatc,
            issue_date=today,
            valid_until=valid_until,
            verification_status=cls.Status.VALID,
        )

        prev_app_status = application.status
        application.status = VerificationApplication.Status.CERTIFICATE_ISSUED
        application.completed_date = today
        application.save(update_fields=['status', 'completed_date', 'updated_at'])

        # Ensure instrument is marked VERIFIED with validity dates
        instrument = application.instrument
        instrument.status = Instrument.Status.VERIFIED
        instrument.last_verified_date = today
        instrument.next_verification_date = valid_until
        instrument.save(update_fields=['status', 'last_verified_date', 'next_verification_date', 'updated_at'])

        AuditLog.log_event(
            actor=actor,
            action=f"Digital Certificate {cert.certificate_number} generated and issued",
            instrument=instrument,
            application=application,
            previous_status=prev_app_status,
            new_status=VerificationApplication.Status.CERTIFICATE_ISSUED,
            remarks=f"Valid until {cert.valid_until:%d %b %Y} | Token: {cert.verification_token[:10]}...",
        )
        return cert


# Alias for external references
Certificate = VerificationCertificate
