from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.exceptions import PermissionDenied

from .models import Instrument, InstrumentCategory
from .forms import InstrumentForm
from verification.models import VerificationApplication, AuditLog


@login_required
def instrument_list_view(request):
    """
    Lists instruments with search and filtering by status, type, category, and district.
    - Owner: sees ONLY own registered instruments
    - Admin: sees all instruments
    - GATC: sees ONLY instruments for applications assigned to this GATC
    - LMO: sees ONLY instruments for applications assigned to this LMO
    """
    user = request.user
    base_qs = Instrument.objects.select_related('category', 'owner')
    if user.is_superuser or user.role == 'ADMIN':
        qs = base_qs.all()
    elif user.role == 'LMO':
        qs = base_qs.filter(verification_applications__assigned_officer=user).distinct()
    elif user.role == 'GATC':
        qs = base_qs.filter(verification_applications__assigned_gatc=user).distinct()
    else:
        qs = base_qs.filter(owner=user)

    # Search & Filter parameters
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    type_filter = request.GET.get('instrument_type', '').strip()
    category_filter = request.GET.get('category', '').strip()
    district_filter = request.GET.get('district', '').strip()

    if q:
        qs = qs.filter(
            Q(instrument_id__icontains=q)
            | Q(instrument_name__icontains=q)
            | Q(serial_number__icontains=q)
            | Q(model_number__icontains=q)
            | Q(manufacturer__icontains=q)
            | Q(owner__username__icontains=q)
        )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if type_filter:
        qs = qs.filter(instrument_type=type_filter)
    if category_filter and category_filter.isdigit():
        qs = qs.filter(category_id=int(category_filter))
    if district_filter:
        qs = qs.filter(district__icontains=district_filter)

    categories = InstrumentCategory.objects.all()
    districts = (
        qs.exclude(district='')
        .values_list('district', flat=True)
        .distinct()
        .order_by('district')
    )

    context = {
        'instruments': qs,
        'total_count': qs.count(),
        'categories': categories,
        'districts': districts,
        'status_choices': Instrument.Status.choices,
        'type_choices': Instrument.InstrumentType.choices,
        'q': q,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'category_filter': category_filter,
        'district_filter': district_filter,
    }
    return render(request, 'instruments/instrument_list.html', context)


@login_required
def instrument_create_view(request):
    """
    Allows an Instrument Owner (or Admin) to register a new weighing/measuring instrument.
    """
    user = request.user
    if not (user.is_superuser or user.role in ['INSTRUMENT_OWNER', 'ADMIN']):
        raise PermissionDenied("Only registered Instrument Owners or Administrators may register instruments.")

    initial_data = {}
    owner_profile = getattr(user, 'owner_profile', None)
    if owner_profile:
        initial_data = {
            'address': owner_profile.address,
            'state': owner_profile.state if owner_profile.state != 'Pending' else '',
            'district': owner_profile.district if owner_profile.district != 'Pending' else '',
        }

    if request.method == 'POST':
        form = InstrumentForm(request.POST, user=user)
        if form.is_valid():
            instrument = form.save(commit=False)
            instrument.owner = user
            instrument.save()
            AuditLog.log_event(
                actor=user,
                action=f"Registered new instrument ({instrument.get_instrument_type_display()})",
                instrument=instrument,
                new_status=instrument.status,
                remarks=f"Serial No: {instrument.serial_number}, Capacity: {instrument.capacity}",
            )
            messages.success(
                request,
                f"Instrument '{instrument.instrument_name}' registered successfully with ID {instrument.instrument_id}."
            )
            return redirect('instruments:detail', pk=instrument.pk)
        else:
            messages.error(request, "Please correct the highlighted errors in the instrument registration form.")
    else:
        form = InstrumentForm(initial=initial_data, user=user)

    return render(request, 'instruments/instrument_form.html', {
        'form': form,
        'is_edit': False,
    })


@login_required
def instrument_detail_view(request, pk):
    """
    Displays full technical specifications, verification applications, and
    immutable audit history for an instrument.
    Strictly enforces backend ownership and assignment permissions.
    """
    user = request.user
    base_qs = Instrument.objects.select_related('category', 'owner')
    if user.is_superuser or user.role == 'ADMIN':
        instrument = get_object_or_404(base_qs, pk=pk)
    elif user.role == 'LMO':
        instrument = get_object_or_404(
            base_qs.filter(verification_applications__assigned_officer=user).distinct(),
            pk=pk
        )
    elif user.role == 'GATC':
        instrument = get_object_or_404(
            base_qs.filter(verification_applications__assigned_gatc=user).distinct(),
            pk=pk
        )
    else:
        instrument = get_object_or_404(base_qs, pk=pk, owner=user)

    applications = (
        VerificationApplication.objects
        .filter(instrument=instrument)
        .select_related('assigned_officer', 'assigned_gatc')
        .order_by('-created_at')
    )
    audit_logs = (
        AuditLog.objects
        .filter(instrument=instrument)
        .select_related('actor', 'application')
        .order_by('-timestamp', '-id')
    )

    return render(request, 'instruments/instrument_detail.html', {
        'instrument': instrument,
        'applications': applications,
        'audit_logs': audit_logs,
    })


@login_required
def instrument_edit_view(request, pk):
    """
    Allows an Owner to edit an instrument BEFORE verification (while in DRAFT,
    ACTIVE, or FAILED status). Admins can also edit instruments.
    """
    user = request.user
    if user.is_superuser or user.role == 'ADMIN':
        instrument = get_object_or_404(Instrument, pk=pk)
    elif user.role == 'INSTRUMENT_OWNER':
        instrument = get_object_or_404(Instrument, pk=pk, owner=user)
    else:
        raise PermissionDenied("You do not have permission to edit this instrument.")

    if not (user.is_superuser or user.role == 'ADMIN') and not instrument.can_owner_edit:
        messages.warning(
            request,
            f"Instrument {instrument.instrument_id} cannot be edited while its status is '{instrument.get_status_display()}'."
        )
        return redirect('instruments:detail', pk=instrument.pk)

    prev_status = instrument.status
    if request.method == 'POST':
        form = InstrumentForm(request.POST, instance=instrument, user=user)
        if form.is_valid():
            updated_inst = form.save()
            AuditLog.log_event(
                actor=user,
                action="Updated instrument technical / location details",
                instrument=updated_inst,
                previous_status=prev_status,
                new_status=updated_inst.status,
                remarks=f"Model: {updated_inst.model_number}, Location: {updated_inst.location}",
            )
            messages.success(request, f"Instrument {updated_inst.instrument_id} updated successfully.")
            return redirect('instruments:detail', pk=updated_inst.pk)
        else:
            messages.error(request, "Please correct the highlighted errors below.")
    else:
        form = InstrumentForm(instance=instrument, user=user)

    return render(request, 'instruments/instrument_form.html', {
        'form': form,
        'instrument': instrument,
        'is_edit': True,
    })
