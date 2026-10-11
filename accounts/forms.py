from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from .models import User, InstrumentOwnerProfile, LMOProfile, GATCProfile

# Standard list of Indian States and Union Territories
INDIAN_STATES = [
    ('', '-- Select State / UT --'),
    ('Andhra Pradesh', 'Andhra Pradesh'),
    ('Assam', 'Assam'),
    ('Bihar', 'Bihar'),
    ('Chandigarh', 'Chandigarh'),
    ('Chhattisgarh', 'Chhattisgarh'),
    ('Delhi', 'Delhi (NCT)'),
    ('Goa', 'Goa'),
    ('Gujarat', 'Gujarat'),
    ('Haryana', 'Haryana'),
    ('Himachal Pradesh', 'Himachal Pradesh'),
    ('Jammu & Kashmir', 'Jammu & Kashmir'),
    ('Jharkhand', 'Jharkhand'),
    ('Karnataka', 'Karnataka'),
    ('Kerala', 'Kerala'),
    ('Madhya Pradesh', 'Madhya Pradesh'),
    ('Maharashtra', 'Maharashtra'),
    ('Odisha', 'Odisha'),
    ('Punjab', 'Punjab'),
    ('Rajasthan', 'Rajasthan'),
    ('Tamil Nadu', 'Tamil Nadu'),
    ('Telangana', 'Telangana'),
    ('Uttar Pradesh', 'Uttar Pradesh'),
    ('Uttarakhand', 'Uttarakhand'),
    ('West Bengal', 'West Bengal'),
]

class UserLoginForm(AuthenticationForm):
    """
    Enhanced authentication form styled with official Government portal controls.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter Username / Registration ID',
            'autocomplete': 'username',
            'id': 'id_username'
        }),
        label="Username / User ID"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter Secure Password',
            'autocomplete': 'current-password',
            'id': 'id_password'
        }),
        label="Password"
    )


class InstrumentOwnerRegistrationForm(forms.ModelForm):
    """
    Self-service registration form for Instrument Owners / Manufacturers / Traders.
    Atomically creates the User account and the InstrumentOwnerProfile.
    """
    # User Account Fields
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. maharashtra_scales'}),
        help_text="Choose a unique username for logging into the portal."
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@enterprise.com'}),
        help_text="Official email for verification alerts and digital certificates."
    )
    first_name = forms.CharField(
        max_length=150,
        label="Authorized Person First Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=150,
        label="Authorized Person Last Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Min 8 characters'}),
        validators=[validate_password],
        help_text="Password must contain at least 8 characters."
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Re-enter password'}),
        label="Confirm Password"
    )

    # InstrumentOwnerProfile Fields
    business_name = forms.CharField(
        max_length=255,
        label="Business / Enterprise Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Registered Firm / Enterprise Name'})
    )
    trade_license_number = forms.CharField(
        max_length=100,
        label="Trade License / Registration Number",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'TL-XXXX-2026'})
    )
    gstin = forms.CharField(
        max_length=15,
        required=False,
        label="GSTIN (Optional)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '27AAAAA0000A1Z5'})
    )
    phone = forms.CharField(
        max_length=15,
        label="Primary Mobile / Phone",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '9876543210'})
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Shop/Factory premises address'}),
        label="Premises Address"
    )
    state = forms.ChoiceField(
        choices=INDIAN_STATES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    district = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Pune / Mumbai / Kamrup'})
    )
    pincode = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '411001'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already registered. Please choose another.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address is already registered.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.INSTRUMENT_OWNER
        user.set_password(self.cleaned_data['password'])
        user.phone = self.cleaned_data.get('phone')
        user._skip_default_profile_signal = True
        if commit:
            user.save()
            InstrumentOwnerProfile.objects.update_or_create(
                user=user,
                defaults={
                    'business_name': self.cleaned_data.get('business_name'),
                    'trade_license_number': self.cleaned_data.get('trade_license_number'),
                    'gstin': self.cleaned_data.get('gstin'),
                    'contact_person': f"{self.cleaned_data.get('first_name')} {self.cleaned_data.get('last_name')}".strip(),
                    'phone': self.cleaned_data.get('phone'),
                    'email': self.cleaned_data.get('email'),
                    'address': self.cleaned_data.get('address'),
                    'state': self.cleaned_data.get('state'),
                    'district': self.cleaned_data.get('district'),
                    'pincode': self.cleaned_data.get('pincode'),
                }
            )
        return user


class PasswordResetEmailForm(forms.Form):
    """
    Password reset request form requiring registered email.
    """
    email = forms.EmailField(
        label="Registered Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your registered email ID'
        })
    )
