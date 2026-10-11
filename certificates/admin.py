from django.contrib import admin, messages
from django.utils.html import format_html
from .models import VerificationCertificate


@admin.register(VerificationCertificate)
class VerificationCertificateAdmin(admin.ModelAdmin):
    list_display = [
        'certificate_number',
        'instrument',
        'owner',
        'issuing_officer',
        'issuing_gatc',
        'issue_date',
        'valid_until',
        'status_badge',
    ]
    list_filter = ['verification_status', 'issue_date', 'valid_until']
    search_fields = [
        'certificate_number',
        'verification_token',
        'certificate_hash',
        'instrument__instrument_id',
        'instrument__serial_number',
        'owner__username',
    ]
    readonly_fields = [
        'certificate_number',
        'application',
        'instrument',
        'owner',
        'issue_date',
        'valid_until',
        'certificate_hash',
        'verification_token',
        'qr_verification_url',
        'revoked_at',
        'revoked_by',
        'generated_at',
    ]
    ordering = ['-issue_date', '-generated_at']
    date_hierarchy = 'issue_date'
    actions = ['revoke_selected_certificates']

    @admin.display(description='Validity Status')
    def status_badge(self, obj):
        eff = obj.effective_status
        if eff == 'VALID':
            return format_html('<span style="color: #059669; font-weight: 700;">✓ VALID</span>')
        if eff == 'REVOKED':
            return format_html('<span style="color: #dc2626; font-weight: 700;">✗ REVOKED</span>')
        return format_html('<span style="color: #b45309; font-weight: 700;">● EXPIRED</span>')

    @admin.action(description='Revoke selected certificates (Administrative Control)')
    def revoke_selected_certificates(self, request, queryset):
        count = 0
        for cert in queryset:
            if cert.verification_status != VerificationCertificate.Status.REVOKED:
                cert.revoke(
                    admin_user=request.user,
                    reason='Revoked by Administrator via Admin Console action',
                )
                count += 1
        self.message_user(request, f"{count} certificate(s) revoked.", messages.WARNING)
