"""
URL configuration for Legal Metrology Online Verification System.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from certificates import views as certificate_views

def health_check(request):
    return HttpResponse("OK", content_type="text/plain")

# Heavy Customization of Django Default Admin Experience
admin.site.site_header = "Legal Metrology Verification System — Government Administration"
admin.site.site_title = "Legal Metrology Admin Portal"
admin.site.index_title = "National Oversight & Regulatory Compliance Control Panel"

urlpatterns = [
    # Health Check Endpoint
    path('health', health_check, name='health'),
    path('health/', health_check, name='health_slash'),

    # Administration Portal
    path('admin/', admin.site.urls),

    # Public QR & Certificate Number Verification Portal (No Login Required)
    path('verify/', certificate_views.public_verify_view, name='public_verify'),
    path('verify/<str:token>/', certificate_views.public_verify_view, name='public_verify_token'),

    # Public and Authentication Pages
    path('', include('accounts.urls', namespace='accounts')),

    # Role-Based Dashboard Engine
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),

    # Modular Domain Apps
    path('instruments/', include('instruments.urls', namespace='instruments')),
    path('verification/', include('verification.urls', namespace='verification')),
    path('certificates/', include('certificates.urls', namespace='certificates')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
]

# Serve media files during local development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom Error Handlers
handler403 = 'accounts.views.custom_permission_denied_view'
handler404 = 'accounts.views.custom_page_not_found_view'
handler500 = 'accounts.views.custom_server_error_view'
