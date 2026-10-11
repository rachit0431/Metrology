from django import forms
from django.utils import timezone
from accounts.forms import INDIAN_STATES
from .models import Instrument, InstrumentCategory


class InstrumentForm(forms.ModelForm):
    """
    Form for Instrument Owners (and Admins) to register or update a weighing/measuring instrument
    prior to verification lock.
    """
    state = forms.ChoiceField(
        choices=INDIAN_STATES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Instrument
        fields = [
            'instrument_name',
            'instrument_type',
            'category',
            'manufacturer',
            'model_number',
            'serial_number',
            'capacity',
            'accuracy_class',
            'year_of_manufacture',
            'location',
            'address',
            'state',
            'district',
            'status',
        ]
        widgets = {
            'instrument_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 60-Tonne Pitless Electronic Weighbridge'
            }),
            'instrument_type': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'manufacturer': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Bharat Precision Scales Ltd.'
            }),
            'model_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. IND-WB-60T-PRO'
            }),
            'serial_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Unique manufacturer serial number'
            }),
            'capacity': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Max 60,000 kg, Min 200 kg, e = 10 kg'
            }),
            'accuracy_class': forms.Select(attrs={'class': 'form-select'}),
            'year_of_manufacture': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1980,
                'max': 2035,
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Counter 1 / Main Dispatch Gate'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Full installation premises address'
            }),
            'district': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Pune / Mumbai / Nagpur'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Owners can only set initial status to DRAFT or ACTIVE when adding/editing
        if self.user and not (self.user.is_superuser or getattr(self.user, 'role', '') == 'ADMIN'):
            self.fields['status'].choices = [
                (Instrument.Status.ACTIVE, 'Active (Ready for Verification)'),
                (Instrument.Status.DRAFT, 'Draft (Save for Later)'),
            ]

    def clean_year_of_manufacture(self):
        year = self.cleaned_data.get('year_of_manufacture')
        current_year = timezone.localdate().year
        if year and (year < 1970 or year > current_year + 1):
            raise forms.ValidationError(f"Year of manufacture must be between 1970 and {current_year}.")
        return year
