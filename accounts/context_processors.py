from .models import User

def metrology_context(request):
    """
    Context processor providing Legal Metrology system constants,
    user role flags, and active portal data to all templates.
    """
    user = getattr(request, 'user', None)
    is_auth = user.is_authenticated if user else False

    return {
        'SYSTEM_NAME': 'Legal Metrology Online Verification System',
        'MINISTRY_NAME': 'Ministry of Consumer Affairs, Food & Public Distribution',
        'DEPARTMENT_NAME': 'Department of Consumer Affairs — Legal Metrology Division',
        'GOV_BADGE': 'Government of India',
        'USER_ROLES': User.Role,
        'user_is_owner': is_auth and (user.role == User.Role.INSTRUMENT_OWNER),
        'user_is_lmo': is_auth and (user.role == User.Role.LMO),
        'user_is_gatc': is_auth and (user.role == User.Role.GATC),
        'user_is_admin': is_auth and (user.role == User.Role.ADMIN or user.is_superuser),
    }
