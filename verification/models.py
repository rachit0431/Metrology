from datetime import timedelta
from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from instruments.models import Instrument


class VerificationApplication(models.Model):
    """
    Statutory application for verification or re-verification under the Legal Metrology Act.
    Includes a strict role-checked workflow state machine.
    """
    class ApplicationType(models.TextChoices):
        INITIAL_VERIFICATION = 'INITIAL_VERIFICATION', _('Initial Verification')
        RE_VERIFICATION = 'RE_VERIFICATION', _('Re-Verification (Periodic / Post-Repair)')

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        SUBMITTED = 'SUBMITTED', _('Submitted')
        UNDER_REVIEW = 'UNDER_REVIEW', _('Under Review')
        ASSIGNED = 'ASSIGNED', _('Assigned to Officer / Lab')
        SCHEDULED = 'SCHEDULED', _('Verification Scheduled')
        INSPECTION_PENDING = 'INSPECTION_PENDING', _('Inspection Pending')
        PASSED = 'PASSED', _('Verification Passed')
        FAILED = 'FAILED', _('Verification Failed')
        CERTIFICATE_ISSUED = 'CERTIFICATE_ISSUED', _('Certificate Issued')
        REJECTED = 'REJECTED', _('Application Rejected')
        CANCELLED = 'CANCELLED', _('Cancelled')

    # Formal State Transition Graph: {current_status: {allowed_next_statuses}}
    ALLOWED_TRANSITIONS = {
        Status.DRAFT: {Status.SUBMITTED, Status.CANCELLED},
        Status.SUBMITTED: {Status.UNDER_REVIEW, Status.ASSIGNED, Status.REJECTED, Status.CANCELLED},
        Status.UNDER_REVIEW: {Status.ASSIGNED, Status.REJECTED, Status.CANCELLED},
        Status.ASSIGNED: {Status.ASSIGNED, Status.SCHEDULED, Status.INSPECTION_PENDING, Status.REJECTED},
        Status.SCHEDULED: {Status.INSPECTION_PENDING, Status.SCHEDULED},
        Status.INSPECTION_PENDING: {Status.PASSED, Status.FAILED},
        Status.PASSED: {Status.CERTIFICATE_ISSUED},
        Status.FAILED: set(),
        Status.CERTIFICATE_ISSUED: set(),
        Status.REJECTED: set(),
        Status.CANCELLED: set(),
    }

    # Role-based allowed target states
    ROLE_ALLOWED_TARGETS = {
        'INSTRUMENT_OWNER': {Status.SUBMITTED, Status.CANCELLED},
        'ADMIN': {
            Status.UNDER_REVIEW,
            Status.ASSIGNED,
            Status.SCHEDULED,
            Status.INSPECTION_PENDING,
            Status.CERTIFICATE_ISSUED,
            Status.REJECTED,
            Status.CANCELLED,
        },
        'GATC': {
            Status.ASSIGNED,
            Status.SCHEDULED,
            Status.INSPECTION_PENDING,
        },
        'LMO': {
            Status.SCHEDULED,
            Status.INSPECTION_PENDING,
            Status.PASSED,
            Status.FAILED,
            Status.CERTIFICATE_ISSUED,
        },
    }

    application_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        verbose_name=_('Application Number')
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name='verification_applications',
        verbose_name=_('Instrument')
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_applications',
        verbose_name=_('Applicant (Owner)')
    )
    application_type = models.CharField(
        max_length=30,
        choices=[
            (ApplicationType.INITIAL_VERIFICATION, _('Initial Verification')),
            (ApplicationType.RE_VERIFICATION, _('Re-Verification (Periodic / Post-Repair)')),
        ],
        default=ApplicationType.INITIAL_VERIFICATION,
        verbose_name=_('Application Type')
    )
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Submitted Timestamp')
    )
    preferred_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Preferred Verification Date')
    )
    scheduled_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Scheduled Verification Date')
    )
    completed_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Verification Completion Date')
    )
    location = models.CharField(
        max_length=255,
        default='',
        verbose_name=_('Verification Location / Premises')
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.SUBMITTED,
        verbose_name=_('Application Status')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Official Remarks / Notes')
    )
    assigned_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lmo_assigned_applications',
        limit_choices_to={'role': 'LMO'},
        verbose_name=_('Assigned LMO Officer')
    )
    assigned_gatc = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gatc_assigned_applications',
        limit_choices_to={'role': 'GATC'},
        verbose_name=_('Assigned GATC Centre')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Verification Application')
        verbose_name_plural = _('Verification Applications')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.application_number} — {self.instrument.instrument_name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if self.status == self.Status.SUBMITTED and not self.submitted_at:
            self.submitted_at = timezone.now()
        if not self.location and self.instrument_id:
            self.location = f"{self.instrument.location}, {self.instrument.address}, {self.instrument.district}"
        super().save(*args, **kwargs)
        if not self.application_number:
            year = timezone.localdate().year
            state_code = (self.instrument.state[:2].upper() if self.instrument and self.instrument.state else 'IN')
            self.application_number = f"VA-{year}-{state_code}-{self.pk:05d}"
            super().save(update_fields=['application_number'])

    # Backward-compatible aliases & profile helpers
    @property
    def assigned_lmo(self):
        return self.assigned_officer

    @assigned_lmo.setter
    def assigned_lmo(self, value):
        from .services import resolve_lmo_user
        self.assigned_officer = resolve_lmo_user(value) if value else None

    @property
    def assigned_gatc_profile(self):
        return getattr(self.assigned_gatc, 'gatc_profile', None) if self.assigned_gatc else None

    @property
    def assigned_lmo_profile(self):
        return getattr(self.assigned_officer, 'lmo_profile', None) if self.assigned_officer else None

    @property
    def scheduled_inspection_date(self):
        return self.scheduled_date

    @scheduled_inspection_date.setter
    def scheduled_inspection_date(self, value):
        self.scheduled_date = value

    @property
    def latest_inspection(self):
        return self.inspections.select_related('inspector').order_by('-created_at', '-id').first()

    def get_eligible_lmos(self, gatc_user=None):
        from .services import get_eligible_lmos_for_application
        return get_eligible_lmos_for_application(self, gatc_user=gatc_user)

    def can_user_inspect(self, user):
        """
        Checks if `user` is an authorized LMO (or Admin) allowed to perform
        digital inspection on this application.
        """
        if not user or not user.is_authenticated:
            return False
        if self.status not in {self.Status.ASSIGNED, self.Status.SCHEDULED, self.Status.INSPECTION_PENDING}:
            latest = self.latest_inspection
            if not (latest and not latest.is_locked):
                return False
        if user.is_superuser or getattr(user, 'role', '') == 'ADMIN':
            return True
        if getattr(user, 'role', '') == 'LMO' and self.assigned_officer_id == user.id:
            return True
        return False

    def get_allowed_next_statuses(self, user):
        """
        Returns the list of valid next statuses that `user` is authorized to trigger
        from the current application status.
        """
        if not user or not getattr(user, 'is_authenticated', False):
            return []
        role = 'ADMIN' if user.is_superuser else getattr(user, 'role', '')
        valid_from_state = self.ALLOWED_TRANSITIONS.get(self.status, set())
        allowed_for_role = self.ROLE_ALLOWED_TARGETS.get(role, set())

        # Ownership & assignment checks
        if role == 'INSTRUMENT_OWNER' and self.applicant_id != user.id:
            return []
        if role == 'LMO' and self.assigned_officer_id != user.id:
            return []
        if role == 'GATC' and self.assigned_gatc_id != user.id:
            return []

        return [st for st in self.Status.values if st in (valid_from_state & allowed_for_role)]

    @transaction.atomic
    def transition_to(
        self,
        new_status,
        actor,
        remarks='',
        assigned_officer=None,
        assigned_gatc=None,
        scheduled_date=None,
    ):
        """
        Delegates to the centralized workflow transition service in verification/services.py.
        """
        from .services import execute_application_transition
        return execute_application_transition(
            application=self,
            new_status=new_status,
            actor=actor,
            remarks=remarks,
            assigned_officer=assigned_officer,
            assigned_gatc=assigned_gatc,
            scheduled_date=scheduled_date,
        )

    def assign_gatc(self, admin_user, gatc, remarks=''):
        """
        Helper for Admin to assign a GATC to the application (sets assigned_gatc, keeps assigned_officer=None).
        """
        return self.transition_to(
            new_status=self.Status.ASSIGNED,
            actor=admin_user,
            assigned_gatc=gatc,
            remarks=remarks,
        )

    def assign_lmo(self, gatc_user, lmo, scheduled_date=None, remarks=''):
        """
        Helper for GATC to assign an eligible LMO officer to the application.
        """
        target = self.Status.SCHEDULED if scheduled_date else self.Status.ASSIGNED
        return self.transition_to(
            new_status=target,
            actor=gatc_user,
            assigned_officer=lmo,
            scheduled_date=scheduled_date,
            remarks=remarks,
        )


class Inspection(models.Model):
    """
    Digital inspection record completed by an authorized Legal Metrology Officer (LMO)
    or Government Approved Test Centre (GATC).
    Completed inspection records are locked against arbitrary editing unless
    unlocked through an authorized administrative correction workflow.
    """
    class Condition(models.TextChoices):
        GOOD_INTACT = 'GOOD_INTACT', _('Satisfactory — Physical & Statutory Seals Intact')
        MINOR_WEAR = 'MINOR_WEAR', _('Operational — Minor Wear Within Operational Norms')
        SEAL_BROKEN = 'SEAL_BROKEN', _('Non-Compliant — Statutory Seal Broken / Tampered')
        DAMAGED_DEFECTIVE = 'DAMAGED_DEFECTIVE', _('Defective — Physical / Load-Cell / Sensor Damage')

    class Result(models.TextChoices):
        PASS = 'PASS', _('PASS — Complies with Metrological Specifications')
        FAIL = 'FAIL', _('FAIL — Non-Compliant / Rectification Required')
        REVIEW_REQUIRED = 'REVIEW_REQUIRED', _('CONDITIONAL / REVIEW REQUIRED — Further Technical Review')

    inspection_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        verbose_name=_('Inspection Number')
    )
    application = models.ForeignKey(
        VerificationApplication,
        on_delete=models.CASCADE,
        related_name='inspections',
        verbose_name=_('Verification Application')
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='conducted_inspections',
        verbose_name=_('Inspecting Officer / Test Centre')
    )
    inspection_date = models.DateField(
        default=timezone.localdate,
        verbose_name=_('Date of Inspection')
    )
    location = models.CharField(
        max_length=255,
        verbose_name=_('Inspection Location / Lab Facility')
    )
    instrument_condition = models.CharField(
        max_length=30,
        choices=Condition.choices,
        default=Condition.GOOD_INTACT,
        verbose_name=_('Instrument & Seal Condition')
    )
    test_parameters = models.TextField(
        verbose_name=_('Test Parameters & Reference Standards Used'),
        help_text=_('Record reference standard weights/measures used, test loads, repeatability, and ambient conditions.')
    )
    observed_readings = models.TextField(
        verbose_name=_('Observed Metrological Readings'),
        help_text=_('Enter actual load vs. indicated readings and observed deviations recorded during testing.')
    )
    remarks = models.TextField(
        verbose_name=_('Inspector Findings & Remarks'),
        help_text=_('Official metrological conclusion, compliance notes, or specific failure reasons.')
    )
    result = models.CharField(
        max_length=25,
        choices=Result.choices,
        verbose_name=_('Final Inspection Result')
    )
    supporting_document = models.FileField(
        upload_to='inspections/documents/%Y/%m/',
        null=True,
        blank=True,
        verbose_name=_('Supporting Test Sheet / Photo (Optional)')
    )
    is_locked = models.BooleanField(
        default=True,
        verbose_name=_('Record Locked (Completed)')
    )
    correction_unlocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unlocked_inspections',
        verbose_name=_('Correction Authorized By')
    )
    correction_reason = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Authorized Correction Reason')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Digital Inspection Record')
        verbose_name_plural = _('Digital Inspection Records')
        ordering = ['-inspection_date', '-created_at']

    def __str__(self):
        return f"{self.inspection_number} — {self.application.application_number} ({self.get_result_display()})"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            orig = Inspection.objects.filter(pk=self.pk).first()
            if orig and orig.is_locked and not getattr(self, '_allow_lock_toggle', False):
                raise PermissionDenied(
                    "Completed inspection records are locked and cannot be modified without "
                    "an authorized administrative correction unlock."
                )
        if not self.location and self.application_id:
            self.location = self.application.location
        super().save(*args, **kwargs)
        if not self.inspection_number:
            year = timezone.localdate().year
            state_code = (
                self.application.instrument.state[:2].upper()
                if self.application and self.application.instrument and self.application.instrument.state
                else 'IN'
            )
            self.inspection_number = f"INSP-{year}-{state_code}-{self.pk:05d}"
            super().save(update_fields=['inspection_number'])

    @transaction.atomic
    def unlock_for_correction(self, admin_user, reason):
        """
        Authorized administrative workflow to unlock a completed inspection for correction.
        """
        if not (admin_user.is_superuser or getattr(admin_user, 'role', '') == 'ADMIN'):
            raise PermissionDenied("Only an Administrator can authorize an inspection correction unlock.")
        if not reason or not reason.strip():
            raise ValidationError("A valid administrative reason is required to unlock an inspection record.")
        self._allow_lock_toggle = True
        self.is_locked = False
        self.correction_unlocked_by = admin_user
        self.correction_reason = reason.strip()
        self.save()
        AuditLog.log_event(
            actor=admin_user,
            action=f"Inspection {self.inspection_number} unlocked for authorized correction",
            instrument=self.application.instrument,
            application=self.application,
            remarks=f"Correction Reason: {self.correction_reason}",
        )


class AuditLog(models.Model):
    """
    Immutable statutory audit trail recording all instrument and verification
    workflow events. Users cannot modify or delete audit history.
    """
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_('Actor / User')
    )
    action = models.CharField(
        max_length=255,
        verbose_name=_('Action Recorded')
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Event Timestamp')
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_('Related Instrument')
    )
    application = models.ForeignKey(
        VerificationApplication,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_('Related Application')
    )
    related_object_repr = models.CharField(
        max_length=255,
        verbose_name=_('Related Object')
    )
    previous_status = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Previous Status')
    )
    new_status = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('New Status')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Remarks')
    )

    class Meta:
        verbose_name = _('Immutable Audit Log')
        verbose_name_plural = _('Immutable Audit Logs')
        ordering = ['-timestamp', '-id']

    def __str__(self):
        actor_name = self.actor.username if self.actor else 'System'
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {actor_name}: {self.action}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionDenied("AuditLog records are immutable and cannot be modified after creation.")
        if not self.related_object_repr:
            if self.application:
                self.related_object_repr = f"Application {self.application.application_number}"
            elif self.instrument:
                self.related_object_repr = f"Instrument {self.instrument.instrument_id or self.instrument.serial_number}"
            else:
                self.related_object_repr = "System Record"
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("AuditLog records are immutable and cannot be deleted.")

    @classmethod
    def log_event(
        cls,
        actor,
        action,
        instrument=None,
        application=None,
        previous_status='',
        new_status='',
        remarks='',
    ):
        if application and not instrument:
            instrument = application.instrument
        related_repr = ''
        if application:
            related_repr = f"Application {application.application_number}"
        elif instrument:
            related_repr = f"Instrument {instrument.instrument_id or instrument.serial_number}"
        return cls.objects.create(
            actor=actor if (actor and getattr(actor, 'is_authenticated', False)) else None,
            action=action,
            instrument=instrument,
            application=application,
            related_object_repr=related_repr,
            previous_status=previous_status or '',
            new_status=new_status or '',
            remarks=remarks or '',
        )
