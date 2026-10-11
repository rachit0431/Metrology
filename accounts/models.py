from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """
    Custom User Model for Legal Metrology Verification System.
    Stores core authentication credentials and central system role.
    """
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', _('System Administrator')
        INSTRUMENT_OWNER = 'INSTRUMENT_OWNER', _('Instrument Owner / Manufacturer / Trader')
        LMO = 'LMO', _('Legal Metrology Officer (LMO)')
        GATC = 'GATC', _('Government Approved Test Centre (GATC)')

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.INSTRUMENT_OWNER,
        help_text=_('Designated operational role determining system permissions.')
    )
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text=_('Primary contact mobile number for official alerts.')
    )
    is_verified = models.BooleanField(
        default=False,
        help_text=_('Indicates whether official credentials/identity have been verified.')
    )

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_owner(self):
        return self.role == self.Role.INSTRUMENT_OWNER

    @property
    def is_lmo(self):
        return self.role == self.Role.LMO

    @property
    def is_gatc(self):
        return self.role == self.Role.GATC

    @property
    def display_name(self):
        full = self.get_full_name().strip()
        return full if full else self.username


class InstrumentOwnerProfile(models.Model):
    """
    Profile for commercial instrument owners, manufacturers, dealers, and traders.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='owner_profile',
        limit_choices_to={'role': User.Role.INSTRUMENT_OWNER}
    )
    business_name = models.CharField(
        max_length=255,
        verbose_name=_('Business / Enterprise Name'),
        help_text=_('Registered enterprise name as per trade license or GSTIN.')
    )
    trade_license_number = models.CharField(
        max_length=100,
        verbose_name=_('Trade License / Establishment Reg. No.'),
        help_text=_('Municipal or state trade license number.')
    )
    gstin = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name=_('GSTIN (Optional)'),
        help_text=_('15-digit Goods and Services Tax Identification Number.')
    )
    contact_person = models.CharField(
        max_length=150,
        verbose_name=_('Authorized Contact Person')
    )
    phone = models.CharField(
        max_length=15,
        verbose_name=_('Primary Phone / Mobile')
    )
    email = models.EmailField(
        verbose_name=_('Official Email Address')
    )
    address = models.TextField(
        verbose_name=_('Premises / Operating Address')
    )
    state = models.CharField(
        max_length=100,
        verbose_name=_('State / UT')
    )
    district = models.CharField(
        max_length=100,
        verbose_name=_('District')
    )
    pincode = models.CharField(
        max_length=10,
        verbose_name=_('PIN Code')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Instrument Owner Profile')
        verbose_name_plural = _('Instrument Owner Profiles')
        ordering = ['business_name']

    def __str__(self):
        return f"{self.business_name} ({self.district}, {self.state})"


class LMOProfile(models.Model):
    """
    Profile for Legal Metrology Officers (LMOs) responsible for field inspections,
    verification, stamping, and enforcement.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='lmo_profile',
        limit_choices_to={'role': User.Role.LMO}
    )
    officer_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('Official Officer ID / Badge No.'),
        help_text=_('Unique government identifier (e.g. LMO-MH-PUN-042).')
    )
    department = models.CharField(
        max_length=200,
        default='Department of Legal Metrology (Weights & Measures)',
        verbose_name=_('Government Department')
    )
    designation = models.CharField(
        max_length=150,
        default='Inspector of Legal Metrology',
        verbose_name=_('Official Designation')
    )
    jurisdiction_state = models.CharField(
        max_length=100,
        verbose_name=_('Jurisdiction State / UT')
    )
    jurisdiction_district = models.CharField(
        max_length=100,
        verbose_name=_('Jurisdiction District')
    )
    jurisdiction_circle = models.CharField(
        max_length=150,
        verbose_name=_('Jurisdiction Circle / Zone / Taluka'),
        help_text=_('Sub-division or circle under officer oversight.')
    )
    office_phone = models.CharField(
        max_length=20,
        verbose_name=_('Office Contact Number')
    )
    official_email = models.EmailField(
        verbose_name=_('Official Government Email (.gov.in / nic.in)')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Legal Metrology Officer (LMO) Profile')
        verbose_name_plural = _('Legal Metrology Officer Profiles')
        ordering = ['jurisdiction_state', 'jurisdiction_district', 'officer_id']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.officer_id} ({self.jurisdiction_district})"


class GATCProfile(models.Model):
    """
    Profile for Government Approved Test Centres (GATCs) authorized to conduct
    statutory testing and calibration of weights, measures, and weighing instruments.
    """
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active / Authorized')
        UNDER_REVIEW = 'UNDER_REVIEW', _('Under Review / Audit')
        SUSPENDED = 'SUSPENDED', _('Suspended / Inactive')

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='gatc_profile',
        limit_choices_to={'role': User.Role.GATC}
    )
    centre_name = models.CharField(
        max_length=255,
        verbose_name=_('Testing Centre / Laboratory Name')
    )
    approval_number = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Statutory Approval / Reg. Number'),
        help_text=_('Official gazette or regulatory recognition number (e.g. GATC/IND/2026/012).')
    )
    accreditation_details = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Accreditation (e.g. NABL / ISO 17025)'),
        help_text=_('Laboratory quality accreditation status.')
    )
    valid_until = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Authorization Validity Date')
    )
    contact_person = models.CharField(
        max_length=150,
        verbose_name=_('Lab Director / Technical Manager')
    )
    phone = models.CharField(
        max_length=20,
        verbose_name=_('Laboratory Phone Number')
    )
    email = models.EmailField(
        verbose_name=_('Official Email')
    )
    address = models.TextField(
        verbose_name=_('Laboratory Facility Address')
    )
    state = models.CharField(
        max_length=100,
        verbose_name=_('State / UT')
    )
    district = models.CharField(
        max_length=100,
        verbose_name=_('District')
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_('Regulatory Authorization Status')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('GATC Profile')
        verbose_name_plural = _('GATC Profiles')
        ordering = ['centre_name']

    def __str__(self):
        return f"{self.centre_name} [{self.approval_number}] - {self.get_status_display()}"
