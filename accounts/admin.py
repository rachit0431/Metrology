from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import User, InstrumentOwnerProfile, LMOProfile, GATCProfile

class InstrumentOwnerProfileInline(admin.StackedInline):
    model = InstrumentOwnerProfile
    can_delete = False
    verbose_name = "Commercial Owner Profile"
    verbose_name_plural = "Commercial Owner Profile"
    extra = 0
    classes = ['collapse']


class LMOProfileInline(admin.StackedInline):
    model = LMOProfile
    can_delete = False
    verbose_name = "Legal Metrology Officer Profile"
    verbose_name_plural = "Legal Metrology Officer Profile"
    extra = 0
    classes = ['collapse']


class GATCProfileInline(admin.StackedInline):
    model = GATCProfile
    can_delete = False
    verbose_name = "Government Approved Test Centre Profile"
    verbose_name_plural = "Government Approved Test Centre Profile"
    extra = 0
    classes = ['collapse']


# ==============================================================================
# Custom User Admin
# ==============================================================================

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """
    Extensively customized User admin for regulatory oversight and governance.
    """
    inlines = [InstrumentOwnerProfileInline, LMOProfileInline, GATCProfileInline]

    list_display = [
        'username',
        'get_full_name_or_user',
        'email',
        'role_badge',
        'phone',
        'is_verified_badge',
        'is_active',
        'date_joined',
    ]
    list_filter = ['role', 'is_active', 'is_verified', 'is_staff', 'date_joined']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'phone']
    ordering = ['-date_joined']
    date_hierarchy = 'date_joined'

    fieldsets = (
        (_('Authentication Credentials'), {
            'fields': ('username', 'password')
        }),
        (_('Personal Information'), {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        (_('Regulatory Role & Status'), {
            'fields': ('role', 'is_verified', 'is_active', 'is_staff', 'is_superuser'),
            'description': 'Role dictates permissions and accessible portal interfaces.'
        }),
        (_('Important Dates'), {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['date_joined', 'last_login']
    actions = ['mark_as_verified', 'activate_users', 'deactivate_users']

    @admin.display(description='Full Name')
    def get_full_name_or_user(self, obj):
        name = obj.get_full_name()
        return name if name else "—"

    @admin.display(description='Role')
    def role_badge(self, obj):
        colors = {
            User.Role.ADMIN: '#1e3a8a',           # Deep Navy Blue
            User.Role.INSTRUMENT_OWNER: '#0284c7', # Slate Blue
            User.Role.LMO: '#0f766e',              # Deep Teal / Emerald
            User.Role.GATC: '#7c3aed',             # Metrology Purple
        }
        bg = colors.get(obj.role, '#475569')
        return format_html(
            '<span style="background-color: {}; color: #ffffff; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600; letter-spacing: 0.3px;">{}</span>',
            bg,
            obj.get_role_display()
        )

    @admin.display(description='Verified')
    def is_verified_badge(self, obj):
        if obj.is_verified:
            return format_html('<span style="color: #059669; font-weight: 600;">✓ Verified</span>')
        return format_html('<span style="color: #94a3b8;">Pending</span>')

    @admin.action(description="Mark selected users as Officially Verified")
    def mark_as_verified(self, request, queryset):
        count = queryset.update(is_verified=True)
        self.message_user(request, f"{count} user(s) successfully marked as verified.")

    @admin.action(description="Activate selected user accounts")
    def activate_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} user account(s) activated.")

    @admin.action(description="Deactivate selected user accounts")
    def deactivate_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} user account(s) deactivated.")


# ==============================================================================
# Instrument Owner Profile Admin
# ==============================================================================

@admin.register(InstrumentOwnerProfile)
class InstrumentOwnerProfileAdmin(admin.ModelAdmin):
    list_display = [
        'business_name',
        'contact_person',
        'trade_license_number',
        'district',
        'state',
        'phone',
        'created_at'
    ]
    list_filter = ['state', 'district', 'created_at']
    search_fields = ['business_name', 'trade_license_number', 'gstin', 'contact_person', 'phone', 'email']
    ordering = ['business_name']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        (_('Enterprise Information'), {
            'fields': ('user', 'business_name', 'trade_license_number', 'gstin')
        }),
        (_('Contact Details'), {
            'fields': ('contact_person', 'phone', 'email')
        }),
        (_('Location & Premises'), {
            'fields': ('address', 'district', 'state', 'pincode')
        }),
        (_('Audit Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ==============================================================================
# Legal Metrology Officer (LMO) Profile Admin
# ==============================================================================

@admin.register(LMOProfile)
class LMOProfileAdmin(admin.ModelAdmin):
    list_display = [
        'officer_id',
        'get_officer_name',
        'designation',
        'jurisdiction_district',
        'jurisdiction_state',
        'office_phone',
        'created_at'
    ]
    list_filter = ['jurisdiction_state', 'jurisdiction_district', 'designation', 'created_at']
    search_fields = ['officer_id', 'user__first_name', 'user__last_name', 'user__username', 'official_email', 'jurisdiction_district']
    ordering = ['jurisdiction_state', 'jurisdiction_district', 'officer_id']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        (_('Official Credentials'), {
            'fields': ('user', 'officer_id', 'department', 'designation')
        }),
        (_('Jurisdiction Authority'), {
            'fields': ('jurisdiction_state', 'jurisdiction_district', 'jurisdiction_circle'),
            'description': 'Defines the legal administrative zone for inspection and verification powers.'
        }),
        (_('Contact Communication'), {
            'fields': ('office_phone', 'official_email')
        }),
        (_('Audit Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Officer Name')
    def get_officer_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


# ==============================================================================
# GATC Profile Admin
# ==============================================================================

@admin.register(GATCProfile)
class GATCProfileAdmin(admin.ModelAdmin):
    list_display = [
        'centre_name',
        'approval_number',
        'status_badge',
        'district',
        'state',
        'valid_until',
        'phone',
    ]
    list_filter = ['status', 'state', 'district', 'valid_until']
    search_fields = ['centre_name', 'approval_number', 'accreditation_details', 'contact_person', 'email']
    ordering = ['centre_name']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']
    actions = ['mark_active', 'mark_under_review', 'mark_suspended']

    fieldsets = (
        (_('Laboratory Identification'), {
            'fields': ('user', 'centre_name', 'approval_number', 'accreditation_details', 'status', 'valid_until')
        }),
        (_('Management & Contact'), {
            'fields': ('contact_person', 'phone', 'email')
        }),
        (_('Facility Location'), {
            'fields': ('address', 'district', 'state')
        }),
        (_('Audit Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            GATCProfile.Status.ACTIVE: '#059669',
            GATCProfile.Status.UNDER_REVIEW: '#d97706',
            GATCProfile.Status.SUSPENDED: '#dc2626',
        }
        bg = colors.get(obj.status, '#64748b')
        return format_html(
            '<span style="background-color: {}; color: #ffffff; padding: 2px 7px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            bg,
            obj.get_status_display()
        )

    @admin.action(description="Mark selected GATCs as Active")
    def mark_active(self, request, queryset):
        queryset.update(status=GATCProfile.Status.ACTIVE)
        self.message_user(request, "Selected test centres marked as Active.")

    @admin.action(description="Mark selected GATCs as Under Review")
    def mark_under_review(self, request, queryset):
        queryset.update(status=GATCProfile.Status.UNDER_REVIEW)
        self.message_user(request, "Selected test centres placed Under Review.")

    @admin.action(description="Mark selected GATCs as Suspended")
    def mark_suspended(self, request, queryset):
        queryset.update(status=GATCProfile.Status.SUSPENDED)
        self.message_user(request, "Selected test centres Suspended.")
