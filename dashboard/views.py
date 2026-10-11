from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from accounts.decorators import admin_required, owner_required, lmo_required, gatc_required
from instruments.models import Instrument
from verification.models import VerificationApplication, AuditLog
from certificates.models import VerificationCertificate


@login_required
def dashboard_index_view(request):
    """
    Central dispatcher that inspects the authenticated user's role
    and routes them to their authorized dashboard shell.
    """
    user = request.user
    if user.is_superuser or user.role == User.Role.ADMIN:
        return redirect('dashboard:admin')
    elif user.role == User.Role.INSTRUMENT_OWNER:
        return redirect('dashboard:owner')
    elif user.role == User.Role.LMO:
        return redirect('dashboard:lmo')
    elif user.role == User.Role.GATC:
        return redirect('dashboard:gatc')
    return redirect('accounts:landing')


@login_required
@owner_required
def owner_dashboard_view(request):
    """
    Instrument Owner Dashboard (Part 2):
    Real database counts:
    - Total Instruments
    - Pending Verification
    - Verified
    - Failed
    - Expiring Soon
    Plus Recent Instruments & Recent Applications tables.
    """
    user = request.user
    today = timezone.localdate()
    thirty_days_later = today + timedelta(days=30)

    user_instruments = Instrument.objects.filter(owner=user)
    total_instruments = user_instruments.count()

    pending_verification = user_instruments.filter(
        status=Instrument.Status.VERIFICATION_PENDING
    ).count()

    verified_instruments = user_instruments.filter(
        status=Instrument.Status.VERIFIED
    ).count()

    failed_instruments = user_instruments.filter(
        status=Instrument.Status.FAILED
    ).count()

    expiring_soon = user_instruments.filter(
        next_verification_date__gte=today,
        next_verification_date__lte=thirty_days_later
    ).count()

    recent_instruments = user_instruments.select_related('category').order_by('-created_at')[:6]
    recent_applications = VerificationApplication.objects.filter(
        applicant=user
    ).select_related('instrument', 'assigned_officer', 'assigned_gatc').order_by('-created_at')[:6]

    profile = getattr(user, 'owner_profile', None)

    context = {
        'total_instruments': total_instruments,
        'pending_verification': pending_verification,
        'pending_applications': pending_verification,
        'verified_instruments': verified_instruments,
        'failed_instruments': failed_instruments,
        'expiring_soon': expiring_soon,
        'recent_instruments': recent_instruments,
        'recent_applications': recent_applications,
        'profile': profile,
    }
    return render(request, 'dashboard/owner_dashboard.html', context)


@login_required
@lmo_required
def lmo_dashboard_view(request):
    """
    Legal Metrology Officer (LMO) Dashboard (Part 2):
    Shows ONLY applications assigned to this officer (`assigned_officer=user`).
    """
    user = request.user
    assigned_apps = VerificationApplication.objects.filter(assigned_officer=user)

    assigned_count = assigned_apps.count()
    pending_inspections = assigned_apps.filter(
        status__in=[
            VerificationApplication.Status.ASSIGNED,
            VerificationApplication.Status.SCHEDULED,
            VerificationApplication.Status.INSPECTION_PENDING,
        ]
    ).count()
    completed_inspections = assigned_apps.filter(
        status__in=[
            VerificationApplication.Status.PASSED,
            VerificationApplication.Status.FAILED,
            VerificationApplication.Status.CERTIFICATE_ISSUED,
        ]
    ).count()

    recent_tasks = (
        assigned_apps
        .select_related('instrument', 'instrument__category', 'applicant')
        .order_by('-created_at')[:15]
    )
    profile = getattr(user, 'lmo_profile', None)

    context = {
        'assigned_applications': assigned_count,
        'pending_inspections': pending_inspections,
        'completed_inspections': completed_inspections,
        'recent_tasks': recent_tasks,
        'profile': profile,
    }
    return render(request, 'dashboard/lmo_dashboard.html', context)


@login_required
@gatc_required
def gatc_dashboard_view(request):
    """
    Government Approved Test Centre (GATC) Dashboard (Part 2):
    Shows ONLY applications assigned to this centre (`assigned_gatc=user`)
    and provides eligible LMO officers for GATC -> LMO assignment.
    """
    user = request.user
    assigned_apps = VerificationApplication.objects.filter(assigned_gatc=user)

    assigned_requests = assigned_apps.count()
    pending_tests = assigned_apps.filter(
        status__in=[
            VerificationApplication.Status.ASSIGNED,
            VerificationApplication.Status.SCHEDULED,
            VerificationApplication.Status.INSPECTION_PENDING,
        ]
    ).count()
    completed_tests = assigned_apps.filter(
        status__in=[
            VerificationApplication.Status.PASSED,
            VerificationApplication.Status.FAILED,
            VerificationApplication.Status.CERTIFICATE_ISSUED,
        ]
    ).count()

    recent_tests = (
        assigned_apps
        .select_related('instrument', 'instrument__category', 'applicant', 'assigned_officer')
        .order_by('-created_at')[:15]
    )
    profile = getattr(user, 'gatc_profile', None)

    eligible_lmos = User.objects.filter(role=User.Role.LMO, is_active=True).select_related('lmo_profile')
    if profile and profile.state and profile.state.lower() != 'pending':
        eligible_lmos = eligible_lmos.filter(lmo_profile__jurisdiction_state__iexact=profile.state)

    context = {
        'assigned_requests': assigned_requests,
        'pending_tests': pending_tests,
        'completed_tests': completed_tests,
        'recent_tests': recent_tests,
        'profile': profile,
        'eligible_lmos': eligible_lmos,
    }
    return render(request, 'dashboard/gatc_dashboard.html', context)


@login_required
@admin_required
def admin_dashboard_view(request):
    """
    System Administration Dashboard (Part 2):
    Provides real-time visibility into users, instruments, verification applications,
    and immutable audit history.
    """
    today = timezone.localdate()
    thirty_days_later = today + timedelta(days=30)

    total_users = User.objects.count()
    owners_count = User.objects.filter(role=User.Role.INSTRUMENT_OWNER).count()
    lmo_count = User.objects.filter(role=User.Role.LMO).count()
    gatc_count = User.objects.filter(role=User.Role.GATC).count()

    total_instruments = Instrument.objects.count()
    pending_applications = VerificationApplication.objects.filter(
        status__in=[
            VerificationApplication.Status.SUBMITTED,
            VerificationApplication.Status.UNDER_REVIEW,
            VerificationApplication.Status.ASSIGNED,
            VerificationApplication.Status.SCHEDULED,
            VerificationApplication.Status.INSPECTION_PENDING,
        ]
    ).count()
    verified_instruments = Instrument.objects.filter(
        status=Instrument.Status.VERIFIED
    ).count()

    expiring_certificates = VerificationCertificate.objects.filter(
        valid_until__gte=today,
        valid_until__lte=thirty_days_later,
        verification_status=VerificationCertificate.Status.VALID
    ).count()

    recent_users = User.objects.order_by('-date_joined')[:6]
    recent_applications = (
        VerificationApplication.objects
        .select_related('instrument', 'applicant', 'assigned_officer', 'assigned_gatc')
        .order_by('-created_at')[:8]
    )
    recent_audit_logs = (
        AuditLog.objects
        .select_related('actor', 'instrument', 'application')
        .order_by('-timestamp', '-id')[:8]
    )

    context = {
        'total_users': total_users,
        'owners_count': owners_count,
        'lmo_count': lmo_count,
        'gatc_count': gatc_count,
        'total_instruments': total_instruments,
        'pending_applications': pending_applications,
        'verified_instruments': verified_instruments,
        'expiring_certificates': expiring_certificates,
        'recent_users': recent_users,
        'recent_applications': recent_applications,
        'recent_audit_logs': recent_audit_logs,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)
