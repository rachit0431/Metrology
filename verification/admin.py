from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from accounts.models import User
from .models import VerificationApplication, Inspection, AuditLog


class ApplicationAuditLogInline(admin.TabularInline):
    model = AuditLog
    fk_name = 'application'
    extra = 0
    can_delete = False
    verbose_name = 'Application Audit Trail Entry'
    verbose_name_plural = 'Immutable Application Audit History'
    readonly_fields = [
        'timestamp',
        'actor',
        'action',
        'previous_status',
        'new_status',
        'remarks',
    ]
    fields = [
        'timestamp',
        'actor',
        'action',
        'previous_status',
        'new_status',
        'remarks',
    ]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VerificationApplication)
class VerificationApplicationAdmin(admin.ModelAdmin):
    """
    Customized Django Admin for VerificationApplication.
    IMPORTANT: Admin can review applications and assign a GATC, but CANNOT directly
    assign an LMO officer (`assigned_officer` is read-only and there is no Assign LMO action).
    LMO assignment happens exclusively through the GATC workflow.
    """
    inlines = [ApplicationAuditLogInline]
    list_display = [
        'application_number',
        'instrument_summary',
        'applicant',
        'application_type',
        'assigned_gatc',
        'assigned_officer',
        'scheduled_date',
        'status_badge',
        'created_at',
    ]
    list_filter = [
        'status',
        'application_type',
        'assigned_gatc',
        'assigned_officer',
        'instrument__instrument_type',
        'instrument__district',
        'scheduled_date',
        'created_at',
    ]
    search_fields = [
        'application_number',
        'instrument__instrument_id',
        'instrument__instrument_name',
        'instrument__serial_number',
        'applicant__username',
        'applicant__email',
        'assigned_gatc__username',
        'assigned_officer__username',
        'location',
    ]
    readonly_fields = [
        'application_number',
        'assigned_officer',
        'submitted_at',
        'created_at',
        'updated_at',
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    actions = [
        'mark_under_review',
        'assign_to_active_gatc',
        'schedule_for_seven_days',
        'move_to_inspection_pending',
        'reject_applications',
    ]

    fieldsets = (
        ('Application Identification', {
            'fields': ('application_number', 'instrument', 'applicant', 'application_type', 'status')
        }),
        ('GATC Assignment & Officer Delegation (GATC assigns LMO)', {
            'fields': ('assigned_gatc', 'assigned_officer', 'location'),
            'description': 'Administration assigns applications to an Approved Test Centre (GATC). The assigned GATC then assigns an eligible LMO Officer.'
        }),
        ('Scheduling & Timeline', {
            'fields': ('preferred_date', 'scheduled_date', 'completed_date', 'submitted_at')
        }),
        ('Official Remarks', {
            'fields': ('remarks',)
        }),
        ('System Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'assigned_gatc':
            kwargs['queryset'] = User.objects.filter(role=User.Role.GATC, is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='Instrument')
    def instrument_summary(self, obj):
        return f"{obj.instrument.instrument_id} — {obj.instrument.instrument_name}"

    @admin.display(description='Workflow Status')
    def status_badge(self, obj):
        color_map = {
            'DRAFT': '#475569',
            'SUBMITTED': '#1e40af',
            'UNDER_REVIEW': '#0369a1',
            'ASSIGNED': '#4338ca',
            'SCHEDULED': '#b45309',
            'INSPECTION_PENDING': '#d97706',
            'PASSED': '#059669',
            'CERTIFICATE_ISSUED': '#047857',
            'FAILED': '#dc2626',
            'REJECTED': '#991b1b',
            'CANCELLED': '#64748b',
        }
        color = color_map.get(obj.status, '#475569')
        return format_html(
            '<span style="color: {}; font-weight: 700;">● {}</span>',
            color,
            obj.get_status_display()
        )

    def save_model(self, request, obj, form, change):
        prev_status = ''
        if change and obj.pk:
            orig = VerificationApplication.objects.filter(pk=obj.pk).first()
            if orig:
                prev_status = orig.status
                # Enforce that Admin cannot directly set assigned_officer
                obj.assigned_officer = orig.assigned_officer
        else:
            obj.assigned_officer = None
        super().save_model(request, obj, form, change)
        if not change:
            AuditLog.log_event(
                actor=request.user,
                action="Application created via Admin Portal",
                instrument=obj.instrument,
                application=obj,
                new_status=obj.status,
                remarks=obj.remarks,
            )
        elif prev_status != obj.status or 'assigned_gatc' in form.changed_data or 'scheduled_date' in form.changed_data:
            AuditLog.log_event(
                actor=request.user,
                action=f"Admin updated application ({', '.join(form.changed_data)})",
                instrument=obj.instrument,
                application=obj,
                previous_status=prev_status,
                new_status=obj.status,
                remarks=obj.remarks,
            )

    @admin.action(description='Place selected applications Under Review')
    def mark_under_review(self, request, queryset):
        count = 0
        for app in queryset:
            if app.status in ['SUBMITTED', 'DRAFT']:
                prev = app.status
                app.status = VerificationApplication.Status.UNDER_REVIEW
                app.save(update_fields=['status', 'updated_at'])
                AuditLog.log_event(
                    actor=request.user,
                    action="Admin action: Placed Under Review",
                    instrument=app.instrument,
                    application=app,
                    previous_status=prev,
                    new_status=app.status,
                )
                count += 1
        self.message_user(request, f"{count} application(s) placed Under Review.", messages.SUCCESS)

    @admin.action(description='Assign selected applications to Active GATC')
    def assign_to_active_gatc(self, request, queryset):
        gatc = User.objects.filter(role=User.Role.GATC, is_active=True).first()
        if not gatc:
            self.message_user(request, "No active GATC found to assign.", messages.ERROR)
            return
        count = 0
        for app in queryset:
            if app.status in ['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED']:
                prev = app.status
                app.assigned_gatc = gatc
                if prev in ['SUBMITTED', 'UNDER_REVIEW']:
                    app.assigned_officer = None
                app.status = VerificationApplication.Status.ASSIGNED
                app.save(update_fields=['assigned_gatc', 'assigned_officer', 'status', 'updated_at'])
                AuditLog.log_event(
                    actor=request.user,
                    action=f"Admin action: Assigned GATC ({gatc.display_name})",
                    instrument=app.instrument,
                    application=app,
                    previous_status=prev,
                    new_status=app.status,
                )
                count += 1
        self.message_user(request, f"{count} application(s) assigned to GATC '{gatc.display_name}'.", messages.SUCCESS)

    @admin.action(description='Schedule verification for +7 days from today')
    def schedule_for_seven_days(self, request, queryset):
        target_date = timezone.localdate() + timezone.timedelta(days=7)
        count = 0
        for app in queryset:
            prev = app.status
            app.scheduled_date = target_date
            app.status = VerificationApplication.Status.SCHEDULED
            app.save(update_fields=['scheduled_date', 'status', 'updated_at'])
            AuditLog.log_event(
                actor=request.user,
                action=f"Admin action: Verification scheduled for {target_date}",
                instrument=app.instrument,
                application=app,
                previous_status=prev,
                new_status=app.status,
            )
            count += 1
        self.message_user(request, f"{count} application(s) scheduled for {target_date}.", messages.SUCCESS)

    @admin.action(description='Move selected applications to Inspection Pending')
    def move_to_inspection_pending(self, request, queryset):
        count = 0
        for app in queryset:
            prev = app.status
            app.status = VerificationApplication.Status.INSPECTION_PENDING
            app.save(update_fields=['status', 'updated_at'])
            AuditLog.log_event(
                actor=request.user,
                action="Admin action: Moved to Inspection Pending",
                instrument=app.instrument,
                application=app,
                previous_status=prev,
                new_status=app.status,
            )
            count += 1
        self.message_user(request, f"{count} application(s) moved to Inspection Pending.", messages.SUCCESS)

    @admin.action(description='Reject selected applications')
    def reject_applications(self, request, queryset):
        count = 0
        for app in queryset:
            prev = app.status
            app.status = VerificationApplication.Status.REJECTED
            app.save(update_fields=['status', 'updated_at'])
            AuditLog.log_event(
                actor=request.user,
                action="Admin action: Application Rejected",
                instrument=app.instrument,
                application=app,
                previous_status=prev,
                new_status=app.status,
            )
            count += 1
        self.message_user(request, f"{count} application(s) rejected.", messages.WARNING)


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = [
        'inspection_number',
        'application',
        'inspector',
        'inspection_date',
        'instrument_condition',
        'result_badge',
        'is_locked',
    ]
    list_filter = ['result', 'instrument_condition', 'is_locked', 'inspection_date']
    search_fields = [
        'inspection_number',
        'application__application_number',
        'application__instrument__instrument_id',
        'application__instrument__serial_number',
        'inspector__username',
        'remarks',
    ]
    readonly_fields = ['inspection_number', 'created_at', 'updated_at']
    actions = ['unlock_selected_inspections']

    @admin.display(description='Inspection Result')
    def result_badge(self, obj):
        colors = {
            'PASS': '#059669',
            'FAIL': '#dc2626',
            'REVIEW_REQUIRED': '#d97706',
        }
        return format_html(
            '<span style="color: {}; font-weight: 700;">● {}</span>',
            colors.get(obj.result, '#475569'),
            obj.get_result_display(),
        )

    @admin.action(description='Authorize correction unlock for selected inspections')
    def unlock_selected_inspections(self, request, queryset):
        count = 0
        for insp in queryset:
            if insp.is_locked:
                insp.unlock_for_correction(
                    admin_user=request.user,
                    reason='Unlocked by Administrator via Django Admin action',
                )
                count += 1
        self.message_user(request, f"{count} inspection record(s) unlocked for correction.", messages.SUCCESS)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Read-only Admin view for Immutable Audit Logs.
    No user (including superuser) can modify or delete audit history through the UI.
    """
    list_display = [
        'timestamp',
        'actor',
        'action',
        'related_object_repr',
        'previous_status',
        'new_status',
    ]
    list_filter = ['new_status', 'timestamp']
    search_fields = [
        'action',
        'related_object_repr',
        'actor__username',
        'remarks',
    ]
    readonly_fields = [
        'actor',
        'action',
        'timestamp',
        'instrument',
        'application',
        'related_object_repr',
        'previous_status',
        'new_status',
        'remarks',
    ]
    ordering = ['-timestamp']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
