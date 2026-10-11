import time
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q

from verification.models import VerificationApplication
from .models import VerificationCertificate


def _check_public_rate_limit(request, limit=30, window_seconds=60):
    """
    Basic IP/session rate limiting for public verification endpoints
    to prevent automated enumeration or abuse.
    """
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    client_ip = forwarded_for.split(',')[0].strip() if forwarded_for else request.META.get('REMOTE_ADDR', 'anon')
    bucket = int(time.time() // window_seconds)
    cache_key = f"pub_verify_rl:{client_ip}:{bucket}"
    current = cache.get(cache_key, 0)
    if current >= limit:
        return False
    cache.set(cache_key, current + 1, timeout=window_seconds + 5)
    return True


@login_required
def certificate_list_view(request):
    user = request.user
    base_qs = VerificationCertificate.objects.select_related(
        'instrument', 'instrument__category', 'owner', 'issuing_officer', 'issuing_gatc', 'application'
    )
    if user.is_superuser or user.role == 'ADMIN':
        qs = base_qs.all()
    elif user.role == 'LMO':
        qs = base_qs.filter(Q(issuing_officer=user) | Q(application__assigned_officer=user))
    elif user.role == 'GATC':
        qs = base_qs.filter(Q(issuing_gatc=user) | Q(application__assigned_gatc=user))
    else:
        qs = base_qs.filter(instrument__owner=user)

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    if q:
        qs = qs.filter(
            Q(certificate_number__icontains=q)
            | Q(instrument__instrument_id__icontains=q)
            | Q(instrument__instrument_name__icontains=q)
            | Q(instrument__serial_number__icontains=q)
        )
    if status_filter:
        qs = qs.filter(verification_status=status_filter)

    return render(request, 'certificates/certificate_list.html', {
        'certificates': qs,
        'total_count': qs.count(),
        'q': q,
        'status_filter': status_filter,
    })


@login_required
def certificate_detail_view(request, certificate_number):
    certificate = get_object_or_404(
        VerificationCertificate.objects.select_related(
            'instrument',
            'instrument__category',
            'instrument__owner',
            'owner',
            'issuing_officer',
            'issuing_gatc',
            'application',
            'revoked_by',
        ),
        certificate_number=certificate_number,
    )
    user = request.user
    if not (
        user.is_superuser
        or user.role == 'ADMIN'
        or certificate.instrument.owner_id == user.id
        or certificate.issuing_officer_id == user.id
        or certificate.issuing_gatc_id == user.id
        or certificate.application.assigned_officer_id == user.id
        or certificate.application.assigned_gatc_id == user.id
    ):
        raise PermissionDenied("You do not have permission to view this internal certificate record.")

    public_verify_path = f"/verify/{certificate.verification_token}/"
    absolute_verify_url = request.build_absolute_uri(public_verify_path)
    qr_svg = certificate.generate_qr_svg(absolute_verify_url=absolute_verify_url, scale=4)

    return render(request, 'certificates/certificate_detail.html', {
        'certificate': certificate,
        'qr_svg': qr_svg,
        'public_verify_path': public_verify_path,
        'absolute_verify_url': absolute_verify_url,
    })


@login_required
def generate_certificate_view(request, application_id):
    """
    Authorized workflow endpoint to generate a digital certificate for a PASSED application.
    """
    if request.method != 'POST':
        return redirect('verification:detail', pk=application_id)

    user = request.user
    application = get_object_or_404(
        VerificationApplication.objects.select_related('instrument', 'instrument__category'),
        pk=application_id,
    )
    if not (
        user.is_superuser
        or user.role == 'ADMIN'
        or (user.role == 'LMO' and application.assigned_officer_id == user.id)
        or (user.role == 'GATC' and application.assigned_gatc_id == user.id)
    ):
        raise PermissionDenied("Only the assigned officer, test centre, or administrator may issue a certificate.")

    try:
        cert = VerificationCertificate.issue_for_application(application=application, actor=user)
        messages.success(request, f"Official Digital Certificate {cert.certificate_number} generated.")
        return redirect('certificates:detail', certificate_number=cert.certificate_number)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect('verification:detail', pk=application.pk)


@login_required
def revoke_certificate_view(request, certificate_number):
    """
    Admin-only endpoint to revoke an issued certificate with an auditable reason.
    """
    if request.method != 'POST':
        return redirect('certificates:detail', certificate_number=certificate_number)

    if not (request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'):
        raise PermissionDenied("Only authorized Administrators may revoke a verification certificate.")

    certificate = get_object_or_404(
        VerificationCertificate.objects.select_related('instrument', 'application'),
        certificate_number=certificate_number,
    )
    reason = request.POST.get('revocation_reason', '').strip()
    try:
        certificate.revoke(admin_user=request.user, reason=reason)
        messages.warning(request, f"Certificate {certificate.certificate_number} has been REVOKED.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, str(exc))

    return redirect('certificates:detail', certificate_number=certificate.certificate_number)


def public_verify_view(request, token=None):
    """
    Public, unauthenticated verification endpoint accessible via:
    1. QR Code scan: /verify/<secure-token>/
    2. Manual lookup by Certificate Number or Verification Token: /verify/?q=LM-2026-000001
    Includes rate limiting and exposes only non-sensitive statutory compliance fields.
    """
    if not _check_public_rate_limit(request):
        return render(request, 'public/verify_certificate.html', {
            'rate_limited': True,
            'searched': True,
            'certificate': None,
        }, status=429)

    query = (token or request.GET.get('q', '') or request.POST.get('q', '')).strip()
    certificate = None
    searched = bool(query)

    if query:
        certificate = (
            VerificationCertificate.objects
            .select_related('instrument', 'instrument__category', 'owner')
            .filter(
                Q(verification_token=query)
                | Q(certificate_number__iexact=query)
            )
            .first()
        )

    organization_name = ''
    if certificate and certificate.owner:
        owner_profile = getattr(certificate.owner, 'owner_profile', None)
        if owner_profile and owner_profile.business_name:
            organization_name = owner_profile.business_name
        else:
            organization_name = certificate.owner.display_name

    return render(request, 'public/verify_certificate.html', {
        'searched': searched,
        'query': query,
        'certificate': certificate,
        'organization_name': organization_name,
        'rate_limited': False,
    })
