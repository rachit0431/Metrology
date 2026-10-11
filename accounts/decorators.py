from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin

def role_required(allowed_roles):
    """
    Decorator for views that checks whether the logged-in user belongs to
    one of the authorized roles.
    If unauthenticated, redirects to login.
    If role does not match, raises PermissionDenied (triggers custom 403 page).
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, "Please sign in to access this official portal.")
                return redirect('accounts:login')

            # Superusers always have full admin privileges
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            if request.user.role not in allowed_roles:
                raise PermissionDenied(
                    f"Access Restricted: Your registered role [{request.user.get_role_display()}] "
                    f"is not authorized to access this department or service."
                )

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def admin_required(view_func):
    return role_required(['ADMIN'])(view_func)


def owner_required(view_func):
    return role_required(['INSTRUMENT_OWNER'])(view_func)


def lmo_required(view_func):
    return role_required(['LMO'])(view_func)


def gatc_required(view_func):
    return role_required(['GATC'])(view_func)


class RoleRequiredMixin(AccessMixin):
    """
    CBV mixin that enforces user role authorization.
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        if self.allowed_roles and request.user.role not in self.allowed_roles:
            raise PermissionDenied(
                f"Access Restricted: Your registered role [{request.user.get_role_display()}] "
                f"is not authorized to view this resource."
            )

        return super().dispatch(request, *args, **kwargs)
