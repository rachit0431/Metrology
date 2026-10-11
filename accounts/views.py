from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import View, CreateView, TemplateView
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator

from .models import User, InstrumentOwnerProfile, LMOProfile, GATCProfile
from .forms import UserLoginForm, InstrumentOwnerRegistrationForm

def get_role_redirect_url(user):
    """
    Computes the role-specific landing dashboard destination.
    """
    if user.is_superuser or user.role == User.Role.ADMIN:
        return reverse('dashboard:admin')
    elif user.role == User.Role.INSTRUMENT_OWNER:
        return reverse('dashboard:owner')
    elif user.role == User.Role.LMO:
        return reverse('dashboard:lmo')
    elif user.role == User.Role.GATC:
        return reverse('dashboard:gatc')
    return reverse('dashboard:index')


class LandingView(TemplateView):
    """
    Public Landing Page for Legal Metrology Online Verification System.
    """
    template_name = 'public/landing.html'

    def get(self, request, *args, **kwargs):
        # If user is already authenticated, redirect to their dashboard
        if request.user.is_authenticated:
            return redirect(get_role_redirect_url(request.user))
        return super().get(request, *args, **kwargs)


class UserLoginView(View):
    """
    Secure Session-Based Login View with Role Routing.
    """
    template_name = 'public/login.html'
    form_class = UserLoginForm

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(get_role_redirect_url(request.user))
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect(get_role_redirect_url(request.user))

        form = self.form_class(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                messages.error(request, "This official account has been deactivated. Please contact the administrator.")
                return render(request, self.template_name, {'form': form})

            login(request, user)
            messages.success(
                request,
                f"Welcome back, {user.display_name}! Authenticated as {user.get_role_display()}."
            )

            # Honor 'next' parameter if present, otherwise role redirect
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(get_role_redirect_url(user))
        else:
            messages.error(request, "Authentication failed. Please verify your username and password.")
            return render(request, self.template_name, {'form': form})


def user_logout_view(request):
    """
    Logs out the current session and redirects to login with confirmation message.
    """
    user_name = request.user.display_name if request.user.is_authenticated else "User"
    logout(request)
    messages.info(request, f"You have been successfully logged out from the Legal Metrology portal.")
    return redirect('accounts:login')


class RegisterOwnerView(View):
    """
    Public Self-Registration for Instrument Owners, Traders, and Manufacturers.
    """
    template_name = 'public/register.html'
    form_class = InstrumentOwnerRegistrationForm

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(get_role_redirect_url(request.user))
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect(get_role_redirect_url(request.user))

        form = self.form_class(request.POST)
        if form.is_valid():
            user = form.save()
            # Log the new user in directly
            login(request, user)
            messages.success(
                request,
                "Registration successful! Your enterprise account is created. Welcome to the Legal Metrology Verification System."
            )
            return redirect('dashboard:owner')
        else:
            messages.error(request, "Please correct the errors in the registration form below.")
            return render(request, self.template_name, {'form': form})


@login_required
def profile_view(request):
    """
    Displays the current user's profile and organizational credentials.
    """
    user = request.user
    context = {'user': user}

    if user.role == User.Role.INSTRUMENT_OWNER:
        context['profile'] = getattr(user, 'owner_profile', None)
    elif user.role == User.Role.LMO:
        context['profile'] = getattr(user, 'lmo_profile', None)
    elif user.role == User.Role.GATC:
        context['profile'] = getattr(user, 'gatc_profile', None)

    return render(request, 'public/profile.html', context)


# ==============================================================================
# Custom Error Handlers
# ==============================================================================

def custom_permission_denied_view(request, exception=None):
    """
    HTTP 403 Forbidden handler.
    """
    context = {
        'error_title': '403 — Access Restricted / Unauthorized',
        'error_message': str(exception) if exception else (
            "You do not possess the statutory credentials or role permissions "
            "required to access this section of the Legal Metrology portal."
        ),
        'user_role': request.user.get_role_display() if request.user.is_authenticated else 'Anonymous Guest',
    }
    return render(request, 'errors/403.html', context, status=403)


def custom_page_not_found_view(request, exception=None):
    """
    HTTP 404 Not Found handler.
    """
    context = {
        'error_title': '404 — Official Page Not Found',
        'error_message': (
            "The requested URL or statutory record could not be located on the "
            "Legal Metrology Online Verification portal. Please verify the URL or return to dashboard."
        ),
    }
    return render(request, 'errors/404.html', context, status=404)


def custom_server_error_view(request):
    """
    HTTP 500 Internal Server Error handler.
    """
    context = {
        'error_title': '500 — Internal Server Error',
        'error_message': (
            "An unexpected error occurred while processing your regulatory request. "
            "The administrative technical team has been notified."
        ),
    }
    return render(request, 'errors/500.html', context, status=500)
