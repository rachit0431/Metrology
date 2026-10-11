from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import User, GATCProfile, LMOProfile
from instruments.models import Instrument


def resolve_gatc_user(gatc_obj):
    """
    Accepts a User (role=GATC) or GATCProfile instance and returns the GATC User.
    """
    if gatc_obj is None:
        return None
    if isinstance(gatc_obj, GATCProfile):
        gatc_obj = gatc_obj.user
    if not isinstance(gatc_obj, User) or getattr(gatc_obj, 'role', '') != User.Role.GATC:
        raise ValidationError("Selected entity is not a valid Government Approved Test Centre (GATC).")
    return gatc_obj


def resolve_lmo_user(lmo_obj):
    """
    Accepts a User (role=LMO) or LMOProfile instance and returns the LMO User.
    """
    if lmo_obj is None:
        return None
    if isinstance(lmo_obj, LMOProfile):
        lmo_obj = lmo_obj.user
    if not isinstance(lmo_obj, User) or getattr(lmo_obj, 'role', '') != User.Role.LMO:
        raise ValidationError("Selected user is not a valid Legal Metrology Officer (LMO).")
    return lmo_obj


def is_lmo_eligible_for_application(application, lmo_user, gatc_user=None):
    """
    Checks whether `lmo_user` belongs to an authorized jurisdiction for `application`
    and `gatc_user`.
    """
    lmo_user = resolve_lmo_user(lmo_user)
    if not lmo_user or not lmo_user.is_active:
        return False

    gatc_user = resolve_gatc_user(gatc_user) if gatc_user else application.assigned_gatc
    lmo_profile = getattr(lmo_user, 'lmo_profile', None)
    gatc_profile = getattr(gatc_user, 'gatc_profile', None) if gatc_user else None

    lmo_state = (getattr(lmo_profile, 'jurisdiction_state', '') or '').strip()
    lmo_district = (getattr(lmo_profile, 'jurisdiction_district', '') or '').strip()
    gatc_state = (getattr(gatc_profile, 'state', '') or '').strip()
    gatc_district = (getattr(gatc_profile, 'district', '') or '').strip()
    inst_state = (getattr(application.instrument, 'state', '') or '').strip() if application and application.instrument_id else ''

    # State-level jurisdiction check against GATC
    if gatc_state and gatc_state.lower() != 'pending' and lmo_state and lmo_state.lower() != 'pending':
        if gatc_state.lower() != lmo_state.lower():
            return False

    # State-level jurisdiction check against Instrument state
    if inst_state and inst_state.lower() != 'pending' and lmo_state and lmo_state.lower() != 'pending':
        if inst_state.lower() != lmo_state.lower():
            return False

    # District-level jurisdiction check when both GATC and LMO specify explicit districts
    if (
        gatc_district
        and gatc_district.lower() not in {'pending', 'all districts'}
        and lmo_district
        and lmo_district.lower() not in {'pending', 'all districts'}
    ):
        if gatc_district.lower() != lmo_district.lower():
            return False

    return True


def get_eligible_lmos_for_application(application, gatc_user=None):
    """
    Returns a queryset of active LMO Users eligible to be assigned by `gatc_user`
    for `application`.
    """
    qs = User.objects.filter(role=User.Role.LMO, is_active=True).select_related('lmo_profile')
    eligible_ids = [
        lmo.id for lmo in qs
        if is_lmo_eligible_for_application(application, lmo, gatc_user=gatc_user)
    ]
    return User.objects.filter(id__in=eligible_ids).select_related('lmo_profile')


@transaction.atomic
def execute_application_transition(
    application,
    new_status,
    actor,
    remarks='',
    assigned_officer=None,
    assigned_gatc=None,
    scheduled_date=None,
):
    """
    Centralized workflow state transition service enforcing the mandatory hierarchy:
    Owner (DRAFT -> SUBMITTED)
      -> Admin (SUBMITTED -> UNDER_REVIEW -> ASSIGNED to GATC only)
      -> GATC (ASSIGNED -> ASSIGNED / SCHEDULED, assigns eligible LMO)
      -> LMO (ASSIGNED -> SCHEDULED -> INSPECTION_PENDING -> PASSED / FAILED)
    """
    from .models import VerificationApplication, AuditLog

    if not actor or not getattr(actor, 'is_authenticated', False):
        raise PermissionDenied("Authentication is required to perform workflow transitions.")

    role = 'ADMIN' if actor.is_superuser else getattr(actor, 'role', '')

    # Strict role & ownership/assignment checks
    if role == 'INSTRUMENT_OWNER':
        if application.applicant_id != actor.id:
            raise PermissionDenied("Owners can only manage their own verification applications.")
        if assigned_gatc is not None or assigned_officer is not None:
            raise PermissionDenied("Instrument Owners are not permitted to assign GATC or LMO officers.")

    elif role == 'ADMIN':
        # CRITICAL RULE: Admin MUST NOT directly assign an application to an LMO
        if assigned_officer is not None:
            raise PermissionDenied(
                "Administrator cannot directly assign an application to an LMO officer. "
                "Admin must assign a GATC, and the GATC assigns an eligible LMO."
            )

    elif role == 'GATC':
        if application.assigned_gatc_id != actor.id:
            raise PermissionDenied("GATC can only access and manage applications assigned to its own test centre.")
        if assigned_gatc is not None and resolve_gatc_user(assigned_gatc).id != actor.id:
            raise PermissionDenied("GATC cannot reassign an application to another GATC.")

    elif role == 'LMO':
        if application.assigned_officer_id != actor.id:
            raise PermissionDenied("LMO can only operate on applications assigned to this officer.")
        if assigned_gatc is not None or assigned_officer is not None:
            raise PermissionDenied("LMO officers cannot reassign GATC or LMO assignments.")

    allowed_targets = application.get_allowed_next_statuses(actor)
    if new_status not in allowed_targets:
        raise PermissionDenied(
            f"Role '{role}' is not authorized to transition application {application.application_number} "
            f"from '{application.get_status_display()}' to '{new_status}'."
        )

    prev_status = application.status
    action_label = f"Status changed from {prev_status} to {new_status}"

    if new_status == VerificationApplication.Status.SUBMITTED:
        application.submitted_at = timezone.now()
        action_label = "Application submitted for verification"
        application.instrument.status = Instrument.Status.VERIFICATION_PENDING
        application.instrument.save(update_fields=['status', 'updated_at'])

    elif new_status == VerificationApplication.Status.UNDER_REVIEW:
        action_label = "Application reviewed and placed Under Review by Administration"

    elif new_status == VerificationApplication.Status.ASSIGNED:
        if role == 'ADMIN':
            gatc_user = resolve_gatc_user(assigned_gatc) if assigned_gatc is not None else application.assigned_gatc
            if not gatc_user:
                raise ValidationError("Please select a Government Approved Test Centre (GATC) to assign this application.")
            application.assigned_gatc = gatc_user
            # After Admin assignment: assigned_gatc = selected GATC, assigned_officer = NULL
            if prev_status in {
                VerificationApplication.Status.SUBMITTED,
                VerificationApplication.Status.UNDER_REVIEW,
            }:
                application.assigned_officer = None
            action_label = f"GATC assigned by Administration (GATC: {gatc_user.display_name})"
        elif role == 'GATC':
            lmo_user = resolve_lmo_user(assigned_officer)
            if not lmo_user:
                raise ValidationError("Please select an eligible Legal Metrology Officer (LMO) to assign.")
            if not is_lmo_eligible_for_application(application, lmo_user, gatc_user=actor):
                raise PermissionDenied(
                    f"LMO '{lmo_user.display_name}' does not belong to an authorized jurisdiction for this GATC / application."
                )
            application.assigned_officer = lmo_user
            if scheduled_date:
                application.scheduled_date = scheduled_date
            action_label = f"LMO assigned by GATC (LMO: {lmo_user.display_name}, GATC: {actor.display_name})"
        else:
            raise PermissionDenied("Only Admin (for GATC) or GATC (for LMO) may perform assignment transitions.")

        application.instrument.status = Instrument.Status.VERIFICATION_PENDING
        application.instrument.save(update_fields=['status', 'updated_at'])

    elif new_status == VerificationApplication.Status.SCHEDULED:
        if role == 'GATC' and assigned_officer is not None:
            lmo_user = resolve_lmo_user(assigned_officer)
            if not is_lmo_eligible_for_application(application, lmo_user, gatc_user=actor):
                raise PermissionDenied(
                    f"LMO '{lmo_user.display_name}' does not belong to an authorized jurisdiction for this GATC / application."
                )
            application.assigned_officer = lmo_user

        if scheduled_date:
            application.scheduled_date = scheduled_date
        if not application.scheduled_date:
            raise ValidationError("A scheduled verification date is required to schedule verification.")
        action_label = f"Verification scheduled for {application.scheduled_date}"
        application.instrument.status = Instrument.Status.VERIFICATION_PENDING
        application.instrument.save(update_fields=['status', 'updated_at'])

    elif new_status == VerificationApplication.Status.INSPECTION_PENDING:
        if scheduled_date:
            application.scheduled_date = scheduled_date
        action_label = "Inspection started — moved to Inspection Pending"
        application.instrument.status = Instrument.Status.VERIFICATION_PENDING
        application.instrument.save(update_fields=['status', 'updated_at'])

    elif new_status == VerificationApplication.Status.PASSED:
        if role == 'LMO' and application.assigned_officer_id != actor.id:
            raise PermissionDenied("Only the assigned LMO officer can mark this verification as PASSED.")
        today = timezone.localdate()
        application.completed_date = today
        validity_months = (
            application.instrument.category.standard_verification_validity_months
            if application.instrument.category_id else 12
        )
        application.instrument.status = Instrument.Status.VERIFIED
        application.instrument.last_verified_date = today
        application.instrument.next_verification_date = today + timedelta(days=validity_months * 30)
        application.instrument.save(
            update_fields=['status', 'last_verified_date', 'next_verification_date', 'updated_at']
        )
        action_label = "Inspection completed: PASSED (Instrument marked VERIFIED)"

    elif new_status == VerificationApplication.Status.CERTIFICATE_ISSUED:
        action_label = "Official Digital Verification Certificate issued"

    elif new_status == VerificationApplication.Status.FAILED:
        if role == 'LMO' and application.assigned_officer_id != actor.id:
            raise PermissionDenied("Only the assigned LMO officer can mark this verification as FAILED.")
        application.completed_date = timezone.localdate()
        application.instrument.status = Instrument.Status.FAILED
        application.instrument.save(update_fields=['status', 'updated_at'])
        action_label = "Inspection completed: FAILED (Instrument marked FAILED)"

    elif new_status == VerificationApplication.Status.REJECTED:
        application.completed_date = timezone.localdate()
        if application.instrument.status == Instrument.Status.VERIFICATION_PENDING:
            application.instrument.status = Instrument.Status.ACTIVE
            application.instrument.save(update_fields=['status', 'updated_at'])
        action_label = "Application rejected by Administration"

    elif new_status == VerificationApplication.Status.CANCELLED:
        if application.instrument.status == Instrument.Status.VERIFICATION_PENDING:
            application.instrument.status = Instrument.Status.ACTIVE
            application.instrument.save(update_fields=['status', 'updated_at'])
        action_label = "Application cancelled"

    application.status = new_status
    if remarks:
        application.remarks = remarks
    application.save()

    AuditLog.log_event(
        actor=actor,
        action=action_label,
        instrument=application.instrument,
        application=application,
        previous_status=prev_status,
        new_status=new_status,
        remarks=remarks,
    )

    return application
