from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class InstrumentCategory(models.Model):
    """
    Standard Legal Metrology Category (e.g., Electronic Weighing Instruments,
    Weighbridges, Flow Meters, Fuel Dispensing Units).
    """
    name = models.CharField(max_length=150, unique=True, verbose_name=_('Category Name'))
    code = models.CharField(max_length=50, unique=True, verbose_name=_('Regulatory Code'))
    description = models.TextField(blank=True, verbose_name=_('Statutory Description'))
    standard_verification_validity_months = models.PositiveIntegerField(
        default=12,
        help_text=_('Configurable validity period in months before re-verification is required.')
    )

    class Meta:
        verbose_name = _('Instrument Category')
        verbose_name_plural = _('Instrument Categories')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Instrument(models.Model):
    """
    Realistic Weighing/Measuring Instrument model under Legal Metrology management.
    """
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        ACTIVE = 'ACTIVE', _('Active (Registered)')
        VERIFICATION_PENDING = 'VERIFICATION_PENDING', _('Verification Pending')
        VERIFIED = 'VERIFIED', _('Verified')
        FAILED = 'FAILED', _('Failed Verification')
        EXPIRED = 'EXPIRED', _('Verification Expired')
        SUSPENDED = 'SUSPENDED', _('Suspended')

    # Alias for backward compatibility with Part 1 references
    VerificationStatus = Status

    class InstrumentType(models.TextChoices):
        COUNTER_SCALE = 'COUNTER_SCALE', _('Electronic Counter / Retail Scale')
        PLATFORM_SCALE = 'PLATFORM_SCALE', _('Platform Weighing Machine')
        WEIGHBRIDGE = 'WEIGHBRIDGE', _('Electronic Road / Rail Weighbridge')
        PRECISION_BALANCE = 'PRECISION_BALANCE', _('Precision / Analytical Balance')
        FUEL_DISPENSER = 'FUEL_DISPENSER', _('Fuel Dispensing Unit (Petrol/Diesel/CNG)')
        FLOW_METER = 'FLOW_METER', _('Liquid / Gas Volumetric Flow Meter')
        LINEAR_MEASURE = 'LINEAR_MEASURE', _('Linear Measure / Measuring Tape')
        CAPACITY_MEASURE = 'CAPACITY_MEASURE', _('Volumetric / Capacity Measure')
        WEIGHT_SET = 'WEIGHT_SET', _('Standard Commercial Bullion / Cast Iron Weights')
        OTHER = 'OTHER', _('Other Regulated Measuring Instrument')

    class AccuracyClass(models.TextChoices):
        CLASS_I = 'CLASS_I', _('Class I (Special Accuracy)')
        CLASS_II = 'CLASS_II', _('Class II (High Accuracy)')
        CLASS_III = 'CLASS_III', _('Class III (Medium Accuracy)')
        CLASS_IV = 'CLASS_IV', _('Class IV (Ordinary Accuracy)')
        NOT_APPLICABLE = 'NA', _('Not Applicable / Unclassified')

    instrument_id = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_('Instrument Registration ID'),
        help_text=_('Unique system registration number (auto-generated if left blank).')
    )
    instrument_name = models.CharField(
        max_length=200,
        verbose_name=_('Instrument / Equipment Name'),
        help_text=_('e.g. Countertop Electronic Scale, 50-Tonne Pitless Weighbridge')
    )
    instrument_type = models.CharField(
        max_length=40,
        choices=InstrumentType.choices,
        default=InstrumentType.COUNTER_SCALE,
        verbose_name=_('Instrument Type')
    )
    category = models.ForeignKey(
        InstrumentCategory,
        on_delete=models.PROTECT,
        related_name='instruments',
        verbose_name=_('Statutory Category')
    )
    manufacturer = models.CharField(
        max_length=200,
        verbose_name=_('Manufacturer Name')
    )
    model_number = models.CharField(
        max_length=100,
        verbose_name=_('Model / Type Approval Number')
    )
    serial_number = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Manufacturer Serial Number')
    )
    capacity = models.CharField(
        max_length=100,
        verbose_name=_('Capacity & Least Count (e)'),
        help_text=_('e.g. Max 30 kg, Min 100 g, e = 5 g')
    )
    accuracy_class = models.CharField(
        max_length=20,
        choices=AccuracyClass.choices,
        default=AccuracyClass.CLASS_III,
        verbose_name=_('Accuracy Class')
    )
    year_of_manufacture = models.PositiveIntegerField(
        default=2025,
        verbose_name=_('Year of Manufacture')
    )
    location = models.CharField(
        max_length=200,
        default='Main Premises',
        verbose_name=_('Site / Bay / Counter Location'),
        help_text=_('Specific placement within premises, e.g. Billing Counter 2, Weighbridge Gate 1')
    )
    address = models.TextField(
        default='',
        verbose_name=_('Premises Address')
    )
    state = models.CharField(
        max_length=100,
        verbose_name=_('State / UT')
    )
    district = models.CharField(
        max_length=100,
        verbose_name=_('District')
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='instruments',
        verbose_name=_('Registered Owner')
    )
    registration_date = models.DateField(
        default=timezone.localdate,
        verbose_name=_('Registration Date')
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_('Instrument Status')
    )
    last_verified_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Last Verified Date')
    )
    next_verification_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Next Verification Due Date')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Weighing & Measuring Instrument')
        verbose_name_plural = _('Weighing & Measuring Instruments')
        ordering = ['-created_at']

    def __init__(self, *args, **kwargs):
        if 'accuracy_or_class' in kwargs and 'accuracy_class' not in kwargs:
            kwargs['accuracy_class'] = kwargs.pop('accuracy_or_class')
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.instrument_id or self.serial_number} — {self.instrument_name} ({self.get_status_display()})"

    @property
    def accuracy_or_class(self):
        return self.accuracy_class

    @accuracy_or_class.setter
    def accuracy_or_class(self, value):
        self.accuracy_class = value

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.instrument_id:
            year = self.registration_date.year if self.registration_date else timezone.localdate().year
            state_code = (self.state[:2].upper() if self.state else 'IN')
            self.instrument_id = f"LM-{state_code}-{year}-{self.pk:05d}"
            super().save(update_fields=['instrument_id'])

    # Backward-compatible properties so Part 1 templates/queries continue working
    @property
    def verification_status(self):
        return self.status

    @verification_status.setter
    def verification_status(self, value):
        self.status = value

    def get_verification_status_display(self):
        return self.get_status_display()

    @property
    def next_verification_due(self):
        return self.next_verification_date

    @next_verification_due.setter
    def next_verification_due(self, value):
        self.next_verification_date = value

    @property
    def installation_address(self):
        return self.address

    @installation_address.setter
    def installation_address(self, value):
        self.address = value

    @property
    def can_owner_edit(self):
        """
        Owners can edit an instrument before it is verified or while in DRAFT,
        ACTIVE, or FAILED state (provided it is not currently locked by a verified certificate).
        """
        return self.status in {
            self.Status.DRAFT,
            self.Status.ACTIVE,
            self.Status.FAILED,
        }

    @property
    def is_expiring_soon(self):
        """Returns True if verification expires within the next 30 days."""
        if not self.next_verification_date:
            return False
        today = timezone.localdate()
        days_remaining = (self.next_verification_date - today).days
        return 0 <= days_remaining <= 30

    @property
    def is_expired(self):
        if not self.next_verification_date:
            return False
        return self.next_verification_date < timezone.localdate()
