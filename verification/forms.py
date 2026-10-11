from django import forms
from django.utils import timezone
from accounts.models import User
from instruments.models import Instrument
from .models import VerificationApplication, Inspection
from .services import get_eligible_lmos_for_application


class VerificationApplicationForm(forms.ModelForm):
    """
    Form for Instrument Owners to create a new Verification / Re-Verification Application.
    """
    submit_action = forms.ChoiceField(
        choices=[
            ('SUBMITTED', 'Submit Immediately for Official Verification'),
            ('DRAFT', 'Save Application as Draft'),
        ],
        initial='SUBMITTED',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Submission Mode"
    )

    class Meta:
        model = VerificationApplication
        fields = [
            'instrument',
            'application_type',
            'preferred_date',
            'location',
            'remarks',
        ]
        widgets = {
            'instrument': forms.Select(attrs={'class': 'form-select'}),
            'application_type': forms.Select(attrs={'class': 'form-select'}),
            'preferred_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Premises / Site location where verification is requested'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional details regarding installation, calibration history, or preferred slot'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user and not (self.user.is_superuser or getattr(self.user, 'role', '') == 'ADMIN'):
            self.fields['instrument'].queryset = Instrument.objects.filter(owner=self.user)
        else:
            self.fields['instrument'].queryset = Instrument.objects.all()

    def clean_preferred_date(self):
        pref_date = self.cleaned_data.get('preferred_date')
        if pref_date and pref_date < timezone.localdate():
            raise forms.ValidationError("Preferred verification date cannot be in the past.")
        return pref_date


class AdminWorkflowForm(forms.Form):
    """
    Administrative workflow form to review applications, assign a GATC,
    schedule verification, and transition application status.
    IMPORTANT: Admin assigns ONLY a GATC; Admin does NOT directly assign an LMO.
    """
    target_status = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Target Workflow Status"
    )
    assigned_gatc = forms.ModelChoiceField(
        queryset=User.objects.filter(role=User.Role.GATC, is_active=True),
        required=False,
        empty_label="-- Select Approved Test Centre (GATC) --",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Assign GATC Laboratory"
    )
    scheduled_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Scheduled Verification Date"
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Enter official administrative review or GATC assignment remarks'
        }),
        label="Administrative Remarks"
    )

    def __init__(self, *args, **kwargs):
        application = kwargs.pop('application')
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        allowed = application.get_allowed_next_statuses(user)
        status_map = dict(VerificationApplication.Status.choices)
        status_map[VerificationApplication.Status.ASSIGNED] = "Assign to GATC Laboratory"
        self.fields['target_status'].choices = [(st, status_map.get(st, st)) for st in allowed]
        self.fields['assigned_gatc'].initial = application.assigned_gatc
        self.fields['scheduled_date'].initial = application.scheduled_date
        self.fields['remarks'].initial = application.remarks


class GATCWorkflowForm(forms.Form):
    """
    Workflow form for an assigned GATC to assign an eligible LMO Officer
    (within authorized jurisdiction) and optionally schedule the verification.
    """
    target_status = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="GATC Action / Workflow Status"
    )
    assigned_officer = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=True,
        empty_label="-- Select Eligible Legal Metrology Officer (LMO) --",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Assign Eligible LMO Officer"
    )
    scheduled_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Scheduled Verification Date (Optional)"
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Enter GATC officer assignment or scheduling notes'
        }),
        label="GATC Assignment Remarks"
    )

    def __init__(self, *args, **kwargs):
        application = kwargs.pop('application')
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        allowed = application.get_allowed_next_statuses(user)
        status_map = dict(VerificationApplication.Status.choices)
        status_map[VerificationApplication.Status.ASSIGNED] = "Assign / Update LMO Officer (Remain Assigned)"
        self.fields['target_status'].choices = [(st, status_map.get(st, st)) for st in allowed]
        self.fields['assigned_officer'].queryset = get_eligible_lmos_for_application(application, gatc_user=user)
        self.fields['assigned_officer'].initial = application.assigned_officer
        self.fields['scheduled_date'].initial = application.scheduled_date
        self.fields['remarks'].initial = application.remarks


class OfficerWorkflowForm(forms.Form):
    """
    Workflow form for assigned LMO Officer to schedule verification,
    move to Inspection Pending, or record PASSED / FAILED outcome.
    """
    target_status = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="LMO Verification Action / Status"
    )
    scheduled_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Scheduled Verification Date"
    )
    remarks = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Record mandatory metrological observations, error margins, or verification findings'
        }),
        label="Official LMO Verification Remarks"
    )

    def __init__(self, *args, **kwargs):
        application = kwargs.pop('application')
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        allowed = application.get_allowed_next_statuses(user)
        status_map = dict(VerificationApplication.Status.choices)
        self.fields['target_status'].choices = [(st, status_map.get(st, st)) for st in allowed]
        self.fields['scheduled_date'].initial = application.scheduled_date


class DigitalInspectionForm(forms.ModelForm):
    """
    Structured Digital Inspection Form for authorized LMO Officers.
    Captures actual metrological test parameters, observed readings, remarks,
    supporting documents, and final result without hardcoding invented legal error limits.
    """
    class Meta:
        model = Inspection
        fields = [
            'inspection_date',
            'location',
            'instrument_condition',
            'test_parameters',
            'observed_readings',
            'remarks',
            'supporting_document',
            'result',
        ]
        widgets = {
            'inspection_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Premises or GATC Laboratory Bay where inspection was conducted'
            }),
            'instrument_condition': forms.Select(attrs={'class': 'form-select'}),
            'test_parameters': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'e.g., Reference Standard Weights Set ID, test points applied (Min, 50%, Max), eccentricity & repeatability checks, ambient conditions'
            }),
            'observed_readings': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 4,
                'placeholder': 'e.g., Load 1.000 kg -> Indicated 1.000 kg (Diff: 0.0 g)\nLoad 10.000 kg -> Indicated 10.002 kg (Diff: +2.0 g)\nLoad 50.000 kg -> Indicated 50.005 kg (Diff: +5.0 g)'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Detailed metrological conclusion, compliance notes, or failure reasons requiring rectification'
            }),
            'supporting_document': forms.ClearableFileInput(attrs={
                'class': 'form-control',
            }),
            'result': forms.Select(attrs={'class': 'form-select fw-semibold'}),
        }
