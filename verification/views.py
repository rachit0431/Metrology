from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from instruments.models import Instrument
from certificates.models import VerificationCertificate
from .models import VerificationApplication, Inspection, AuditLog
from .forms import (
    VerificationApplicationForm,
    AdminWorkflowForm,
    GATCWorkflowForm,
    OfficerWorkflowForm,
    DigitalInspectionForm,
)


def _get_scoped_application_or_404(user, pk):
    base_qs = VerificationApplication.objects.select_related(
        'instrument', 'instrument__category', 'applicant', 'assigned_officer', 'assigned_gatc'
    )
    if user.is_superuser or user.role == 'ADMIN':
        return get_object_or_404(base_qs, pk=pk)
    if user.role == 'LMO':
        return get_object_or_404(base_qs, pk=pk, assigned_officer=user)
    if user.role == 'GATC':
        return get_object_or_404(base_qs, pk=pk, assigned_gatc=user)
    return get_object_or_404(base_qs, pk=pk, applicant=user)


@login_required
def application_list_view(request):
    """
    Role-scoped list of Verification Applications with search and filtering:
    - Admin: all applications
    - GATC: ONLY applications assigned to this GATC centre
    - LMO: ONLY applications assigned to this LMO officer
    - Owner: ONLY applications submitted by this owner
    """
    user = request.user
    base_qs = VerificationApplication.objects.select_related(
        'instrument', 'instrument__category', 'applicant', 'assigned_officer', 'assigned_gatc'
    )

    if user.is_superuser or user.role == 'ADMIN':
        qs = base_qs.all()
    elif user.role == 'LMO':
        qs = base_qs.filter(assigned_officer=user)
    elif user.role == 'GATC':
        qs = base_qs.filter(assigned_gatc=user)
    else:
        qs = base_qs.filter(applicant=user)

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    type_filter = request.GET.get('application_type', '').strip()
    district_filter = request.GET.get('district', '').strip()
    gatc_filter = request.GET.get('assigned_gatc', '').strip()
    officer_filter = request.GET.get('assigned_officer', '').strip()

    if q:
        qs = qs.filter(
            Q(application_number__icontains=q)
            | Q(instrument__instrument_name__icontains=q)
            | Q(instrument__serial_number__icontains=q)
            | Q(instrument__instrument_id__icontains=q)
            | Q(applicant__username__icontains=q)
            | Q(location__icontains=q)
        )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if type_filter:
        qs = qs.filter(application_type=type_filter)
    if district_filter:
        qs = qs.filter(instrument__district__icontains=district_filter)
    if gatc_filter.isdigit():
        qs = qs.filter(assigned_gatc_id=int(gatc_filter))
    if officer_filter.isdigit():
        qs = qs.filter(assigned_officer_id=int(officer_filter))

    context = {
        'applications': qs,
        'total_count': qs.count(),
        'status_choices': VerificationApplication.Status.choices,
        'type_choices': [
            (VerificationApplication.ApplicationType.INITIAL_VERIFICATION, 'Initial Verification'),
            (VerificationApplication.ApplicationType.RE_VERIFICATION, 'Re-Verification'),
        ],
        'q': q,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'district_filter': district_filter,
        'gatc_filter': gatc_filter,
        'officer_filter': officer_filter,
    }
    return render(request, 'verification/application_list.html', context)


@login_required
def application_create_view(request, instrument_id=None):
    """
    Allows an Instrument Owner (or Admin) to create and submit a verification
    or re-verification application.
    """
    user = request.user
    if not (user.is_superuser or user.role in ['INSTRUMENT_OWNER', 'ADMIN']):
        raise PermissionDenied("Only Instrument Owners or Administrators may create verification applications.")

    selected_instrument = None
    if instrument_id:
        if user.is_superuser or user.role == 'ADMIN':
            selected_instrument = get_object_or_404(Instrument, pk=instrument_id)
        else:
            selected_instrument = get_object_or_404(Instrument, pk=instrument_id, owner=user)

    initial_data = {}
    if selected_instrument:
        initial_data['instrument'] = selected_instrument
        initial_data['location'] = f"{selected_instrument.location}, {selected_instrument.address}, {selected_instrument.district}"
        if (
            selected_instrument.last_verified_date
            or selected_instrument.status in {Instrument.Status.FAILED, Instrument.Status.EXPIRED}
            or selected_instrument.verification_applications.exists()
        ):
            initial_data['application_type'] = VerificationApplication.ApplicationType.RE_VERIFICATION
        else:
            initial_data['application_type'] = VerificationApplication.ApplicationType.INITIAL_VERIFICATION

    if request.method == 'POST':
        form = VerificationApplicationForm(request.POST, user=user)
        if form.is_valid():
            application = form.save(commit=False)
            application.applicant = application.instrument.owner if (user.is_superuser or user.role == 'ADMIN') else user
            submit_mode = form.cleaned_data.get('submit_action', 'SUBMITTED')
            application.status = (
                VerificationApplication.Status.DRAFT
                if submit_mode == 'DRAFT'
                else VerificationApplication.Status.SUBMITTED
            )
            application.assigned_gatc = None
            application.assigned_officer = None
            if application.status == VerificationApplication.Status.SUBMITTED:
                application.submitted_at = timezone.now()
            application.save()

            AuditLog.log_event(
                actor=user,
                action="Verification application created",
                instrument=application.instrument,
                application=application,
                new_status=application.status,
                remarks=f"Type: {application.get_application_type_display()}",
            )

            if application.status == VerificationApplication.Status.SUBMITTED:
                application.instrument.status = Instrument.Status.VERIFICATION_PENDING
                application.instrument.save(update_fields=['status', 'updated_at'])
                AuditLog.log_event(
                    actor=user,
                    action="Application submitted for official verification",
                    instrument=application.instrument,
                    application=application,
                    previous_status=VerificationApplication.Status.DRAFT,
                    new_status=VerificationApplication.Status.SUBMITTED,
                    remarks=application.remarks,
                )
                messages.success(
                    request,
                    f"Verification application {application.application_number} submitted successfully."
                )
            else:
                messages.info(
                    request,
                    f"Application {application.application_number} saved as Draft. You can submit it when ready."
                )
            return redirect('verification:detail', pk=application.pk)
        else:
            messages.error(request, "Please correct the highlighted errors in the application form.")
    else:
        form = VerificationApplicationForm(initial=initial_data, user=user)

    return render(request, 'verification/application_form.html', {
        'form': form,
        'selected_instrument': selected_instrument,
    })


@login_required
def application_detail_view(request, pk):
    """
    Displays application details, workflow progress, GATC -> LMO assignment controls,
    role-specific state transition controls, and immutable audit trail.
    """
    user = request.user
    application = _get_scoped_application_or_404(user, pk)

    allowed_transitions = application.get_allowed_next_statuses(user)
    admin_form = None
    gatc_form = None
    officer_form = None

    if (user.is_superuser or user.role == 'ADMIN') and allowed_transitions:
        admin_form = AdminWorkflowForm(application=application, user=user)
    elif user.role == 'GATC' and allowed_transitions:
        gatc_form = GATCWorkflowForm(application=application, user=user)
    elif user.role == 'LMO' and allowed_transitions:
        officer_form = OfficerWorkflowForm(application=application, user=user)

    inspections = application.inspections.select_related('inspector', 'correction_unlocked_by').order_by('-created_at', '-id')
    latest_inspection = inspections.first()
    certificate = getattr(application, 'certificate', None)

    audit_logs = (
        AuditLog.objects
        .filter(application=application)
        .select_related('actor')
        .order_by('-timestamp', '-id')
    )

    workflow_steps = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Admin Review'),
        ('ASSIGNED', 'GATC / LMO Assigned'),
        ('SCHEDULED', 'Scheduled'),
        ('INSPECTION_PENDING', 'Inspection Pending'),
        ('PASSED', 'Passed'),
    ]

    return render(request, 'verification/application_detail.html', {
        'application': application,
        'allowed_transitions': allowed_transitions,
        'admin_form': admin_form,
        'gatc_form': gatc_form,
        'officer_form': officer_form,
        'inspections': inspections,
        'latest_inspection': latest_inspection,
        'certificate': certificate,
        'can_inspect': application.can_user_inspect(user),
        'audit_logs': audit_logs,
        'workflow_steps': workflow_steps,
    })


@login_required
def application_transition_view(request, pk):
    """
    Handles role-validated workflow transitions for a VerificationApplication.
    Enforces:
    - Admin assigns ONLY GATC (never directly assigns LMO)
    - GATC assigns ONLY eligible LMO within jurisdiction
    - LMO schedules verification, starts inspection, and marks PASSED / FAILED
    - Owner can only submit or cancel own DRAFT application
    """
    if request.method != 'POST':
        return redirect('verification:detail', pk=pk)

    user = request.user
    application = _get_scoped_application_or_404(user, pk)

    target_status = request.POST.get('target_status', '').strip()
    remarks = request.POST.get('remarks', '').strip()
    raw_officer_id = request.POST.get('assigned_officer', '').strip()
    raw_gatc_id = request.POST.get('assigned_gatc', '').strip()
    sched_str = request.POST.get('scheduled_date', '').strip()

    assigned_officer = None
    assigned_gatc = None
    scheduled_date = None

    if sched_str:
        try:
            scheduled_date = timezone.datetime.strptime(sched_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Invalid scheduled date format.")
            return redirect('verification:detail', pk=application.pk)

    if user.is_superuser or user.role == 'ADMIN':
        # CRITICAL RULE: Admin MUST NOT directly assign an LMO
        if raw_officer_id:
            raise PermissionDenied(
                "Administrator cannot directly assign an application to an LMO officer. "
                "Admin must assign a GATC, and the GATC assigns an eligible LMO."
            )
        if raw_gatc_id.isdigit():
            assigned_gatc = User.objects.filter(pk=int(raw_gatc_id), role=User.Role.GATC, is_active=True).first()
            if not assigned_gatc:
                messages.error(request, "Selected GATC centre is invalid or inactive.")
                return redirect('verification:detail', pk=application.pk)

    elif user.role == 'GATC':
        if raw_gatc_id and (not raw_gatc_id.isdigit() or int(raw_gatc_id) != user.id):
            raise PermissionDenied("GATC cannot reassign an application to another GATC.")
        if raw_officer_id:
            if not raw_officer_id.isdigit():
                messages.error(request, "Invalid LMO officer selection.")
                return redirect('verification:detail', pk=application.pk)
            assigned_officer = User.objects.filter(pk=int(raw_officer_id), role=User.Role.LMO, is_active=True).first()
            if not assigned_officer:
                messages.error(request, "Selected LMO officer is invalid or inactive.")
                return redirect('verification:detail', pk=application.pk)

    elif user.role == 'LMO':
        if raw_gatc_id or raw_officer_id:
            raise PermissionDenied("LMO officers cannot assign or modify GATC/LMO assignments.")

    else:
        # INSTRUMENT_OWNER
        if raw_gatc_id or raw_officer_id:
            raise PermissionDenied("Instrument Owners are not permitted to assign GATC or LMO officers.")

    try:
        application.transition_to(
            new_status=target_status,
            actor=user,
            remarks=remarks,
            assigned_officer=assigned_officer,
            assigned_gatc=assigned_gatc,
            scheduled_date=scheduled_date,
        )
        messages.success(
            request,
            f"Application {application.application_number} updated to '{application.get_status_display()}'."
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    except PermissionDenied as exc:
        messages.error(request, str(exc))

    return redirect('verification:detail', pk=application.pk)


@login_required
def gatc_assign_lmo_view(request, pk):
    """
    Dedicated action view for a GATC to assign an eligible LMO Officer to an
    application assigned to that GATC (from the GATC Dashboard or Application Detail).
    """
    if request.method != 'POST':
        return redirect('verification:detail', pk=pk)

    user = request.user
    if getattr(user, 'role', '') != 'GATC':
        raise PermissionDenied("Only a Government Approved Test Centre (GATC) may assign an LMO officer.")

    application = _get_scoped_application_or_404(user, pk)
    raw_officer_id = request.POST.get('assigned_officer', '').strip()
    sched_str = request.POST.get('scheduled_date', '').strip()
    remarks = request.POST.get('remarks', '').strip() or "Assigned to LMO by GATC"

    if not raw_officer_id.isdigit():
        messages.error(request, "Please select an eligible Legal Metrology Officer (LMO).")
        return redirect(request.POST.get('next') or 'dashboard:gatc')

    lmo_user = get_object_or_404(User, pk=int(raw_officer_id), role=User.Role.LMO, is_active=True)
    scheduled_date = None
    if sched_str:
        try:
            scheduled_date = timezone.datetime.strptime(sched_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Invalid scheduled date format.")
            return redirect(request.POST.get('next') or 'dashboard:gatc')

    try:
        application.assign_lmo(
            gatc_user=user,
            lmo=lmo_user,
            scheduled_date=scheduled_date,
            remarks=remarks,
        )
        messages.success(
            request,
            f"LMO Officer '{lmo_user.display_name}' assigned to application {application.application_number}."
        )
    except (ValidationError, PermissionDenied) as exc:
        err_msg = "; ".join(exc.messages) if hasattr(exc, 'messages') else str(exc)
        messages.error(request, err_msg)

    next_url = request.POST.get('next', '').strip()
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('verification:detail', pk=application.pk)


@login_required
@transaction.atomic
def perform_inspection_view(request, pk):
    """
    Allows an assigned LMO Officer or Administrator to record a structured
    Digital Inspection for an application.
    """
    user = request.user
    application = _get_scoped_application_or_404(user, pk)

    if not application.can_user_inspect(user):
        raise PermissionDenied(
            "You are not authorized to perform a digital inspection on this application, "
            "or the application is not in an inspectable state."
        )

    existing_inspection = application.latest_inspection
    is_correction_mode = bool(existing_inspection and not existing_inspection.is_locked)

    if existing_inspection and existing_inspection.is_locked and application.status in {
        VerificationApplication.Status.PASSED,
        VerificationApplication.Status.FAILED,
        VerificationApplication.Status.CERTIFICATE_ISSUED,
    }:
        messages.warning(
            request,
            f"Inspection {existing_inspection.inspection_number} is already completed and locked. "
            "An Administrator must authorize a correction unlock before it can be edited."
        )
        return redirect('verification:inspection_detail', inspection_id=existing_inspection.pk)

    if request.method == 'POST':
        form = DigitalInspectionForm(
            request.POST,
            request.FILES,
            instance=existing_inspection if is_correction_mode else None,
        )
        if form.is_valid():
            inspection = form.save(commit=False)
            inspection.application = application
            inspection.inspector = user
            inspection.is_locked = True
            if is_correction_mode:
                inspection._allow_lock_toggle = True
            inspection.save()

            AuditLog.log_event(
                actor=user,
                action=(
                    f"Digital Inspection {inspection.inspection_number} corrected & re-locked ({inspection.result})"
                    if is_correction_mode
                    else f"Digital Inspection {inspection.inspection_number} recorded ({inspection.result})"
                ),
                instrument=application.instrument,
                application=application,
                previous_status=application.status,
                new_status=inspection.result,
                remarks=f"Condition: {inspection.get_instrument_condition_display()} | {inspection.remarks}",
            )

            # Advance workflow according to inspection result
            if application.status in {
                VerificationApplication.Status.ASSIGNED,
                VerificationApplication.Status.SCHEDULED,
            }:
                application.status = VerificationApplication.Status.INSPECTION_PENDING
                application.save(update_fields=['status', 'updated_at'])

            if inspection.result == Inspection.Result.PASS:
                if application.status == VerificationApplication.Status.INSPECTION_PENDING:
                    application.transition_to(
                        new_status=VerificationApplication.Status.PASSED,
                        actor=user,
                        remarks=inspection.remarks,
                    )
                VerificationCertificate.issue_for_application(application=application, actor=user)
                cert = getattr(application, 'certificate', None)
                messages.success(
                    request,
                    f"Inspection {inspection.inspection_number} recorded as PASS. "
                    f"Digital Certificate {cert.certificate_number if cert else ''} has been issued."
                )
            elif inspection.result == Inspection.Result.FAIL:
                if application.status == VerificationApplication.Status.INSPECTION_PENDING:
                    application.transition_to(
                        new_status=VerificationApplication.Status.FAILED,
                        actor=user,
                        remarks=inspection.remarks,
                    )
                else:
                    application.status = VerificationApplication.Status.FAILED
                    application.completed_date = timezone.localdate()
                    application.remarks = inspection.remarks
                    application.save(update_fields=['status', 'completed_date', 'remarks', 'updated_at'])
                    application.instrument.status = Instrument.Status.FAILED
                    application.instrument.save(update_fields=['status', 'updated_at'])
                messages.warning(
                    request,
                    f"Inspection {inspection.inspection_number} recorded as FAIL. "
                    "The Owner has been notified of the observations and may submit a Re-Verification request after rectification."
                )
            else:
                application.remarks = inspection.remarks
                application.save(update_fields=['remarks', 'updated_at'])
                messages.info(
                    request,
                    f"Inspection {inspection.inspection_number} logged as Conditional / Review Required."
                )

            return redirect('verification:inspection_detail', inspection_id=inspection.pk)
        else:
            messages.error(request, "Please correct the highlighted fields in the Digital Inspection form.")
    else:
        if is_correction_mode:
            form = DigitalInspectionForm(instance=existing_inspection)
        else:
            form = DigitalInspectionForm(initial={
                'inspection_date': application.scheduled_date or timezone.localdate(),
                'location': application.location or f"{application.instrument.location}, {application.instrument.address}",
                'instrument_condition': Inspection.Condition.GOOD_INTACT,
            })

    return render(request, 'verification/inspection_form.html', {
        'application': application,
        'instrument': application.instrument,
        'form': form,
        'is_correction_mode': is_correction_mode,
        'existing_inspection': existing_inspection,
    })


@login_required
def inspection_detail_view(request, inspection_id):
    """
    Displays the official Digital Inspection Report for an application.
    """
    inspection = get_object_or_404(
        Inspection.objects.select_related(
            'application',
            'application__instrument',
            'application__instrument__category',
            'application__applicant',
            'inspector',
            'correction_unlocked_by',
        ),
        pk=inspection_id,
    )
    _get_scoped_application_or_404(request.user, inspection.application_id)

    return render(request, 'verification/inspection_detail.html', {
        'inspection': inspection,
        'application': inspection.application,
        'instrument': inspection.application.instrument,
    })


@login_required
def unlock_inspection_view(request, inspection_id):
    """
    Authorized Admin-only workflow to unlock a completed inspection record for correction.
    """
    if request.method != 'POST':
        return redirect('verification:inspection_detail', inspection_id=inspection_id)

    if not (request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'):
        raise PermissionDenied("Only an Administrator may authorize an inspection correction unlock.")

    inspection = get_object_or_404(
        Inspection.objects.select_related('application', 'application__instrument'),
        pk=inspection_id,
    )
    reason = request.POST.get('correction_reason', '').strip()
    try:
        inspection.unlock_for_correction(admin_user=request.user, reason=reason)
        messages.success(
            request,
            f"Inspection {inspection.inspection_number} unlocked for correction. "
            "The assigned inspector or administrator can now update the inspection record."
        )
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, str(exc))

    return redirect('verification:inspection_detail', inspection_id=inspection.pk)
