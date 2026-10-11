from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import InstrumentCategory, Instrument
from verification.models import AuditLog


@admin.register(InstrumentCategory)
class InstrumentCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'standard_verification_validity_months']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = [
        'instrument_id',
        'instrument_name',
        'instrument_type',
        'category',
        'serial_number',
        'owner',
        'status_badge',
        'district',
        'state',
        'next_verification_date',
    ]
    list_filter = ['status', 'instrument_type', 'category', 'accuracy_class', 'state', 'district']
    search_fields = [
        'instrument_id',
        'instrument_name',
        'serial_number',
        'model_number',
        'manufacturer',
        'owner__username',
        'owner__first_name',
        'district',
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    readonly_fields = ['instrument_id', 'created_at', 'updated_at']
    actions = ['mark_active', 'mark_suspended', 'mark_expired']

    fieldsets = (
        (_('Registration & Ownership'), {
            'fields': (
                'instrument_id',
                'owner',
                'instrument_name',
                'instrument_type',
                'category',
                'registration_date',
            )
        }),
        (_('Metrological & Manufacturing Specifications'), {
            'fields': (
                'manufacturer',
                'model_number',
                'serial_number',
                'capacity',
                'accuracy_class',
                'year_of_manufacture',
            )
        }),
        (_('Verification Lifecycle'), {
            'fields': ('status', 'last_verified_date', 'next_verification_date')
        }),
        (_('Physical Location'), {
            'fields': ('location', 'address', 'district', 'state')
        }),
        (_('Audit Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            Instrument.Status.VERIFIED: '#059669',
            Instrument.Status.VERIFICATION_PENDING: '#d97706',
            Instrument.Status.ACTIVE: '#0284c7',
            Instrument.Status.DRAFT: '#64748b',
            Instrument.Status.FAILED: '#dc2626',
            Instrument.Status.EXPIRED: '#b91c1c',
            Instrument.Status.SUSPENDED: '#475569',
        }
        bg = colors.get(obj.status, '#475569')
        return format_html(
            '<span style="background-color: {}; color: #ffffff; padding: 2px 7px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            bg,
            obj.get_status_display()
        )

    @admin.action(description="Mark selected instruments as Active")
    def mark_active(self, request, queryset):
        for inst in queryset:
            prev = inst.status
            inst.status = Instrument.Status.ACTIVE
            inst.save(update_fields=['status', 'updated_at'])
            AuditLog.log_event(
                actor=request.user,
                action="Admin action: Marked instrument Active",
                instrument=inst,
                previous_status=prev,
                new_status=inst.status,
            )
        self.message_user(request, f"{queryset.count()} instrument(s) marked as Active.")

    @admin.action(description="Mark selected instruments as Suspended")
    def mark_suspended(self, request, queryset):
        for inst in queryset:
            prev = inst.status
            inst.status = Instrument.Status.SUSPENDED
            inst.save(update_fields=['status', 'updated_at'])
            AuditLog.log_event(
                actor=request.user,
                action="Admin action: Suspended instrument",
                instrument=inst,
                previous_status=prev,
                new_status=inst.status,
            )
        self.message_user(request, f"{queryset.count()} instrument(s) marked as Suspended.")

    @admin.action(description="Mark selected instruments as Expired")
    def mark_expired(self, request, queryset):
        for inst in queryset:
            prev = inst.status
            inst.status = Instrument.Status.EXPIRED
            inst.save(update_fields=['status', 'updated_at'])
            AuditLog.log_event(
                actor=request.user,
                action="Admin action: Marked instrument Expired",
                instrument=inst,
                previous_status=prev,
                new_status=inst.status,
            )
        self.message_user(request, f"{queryset.count()} instrument(s) marked as Expired.")
