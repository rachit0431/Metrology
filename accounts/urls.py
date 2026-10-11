from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    # Public Portal Landing Page
    path('', views.LandingView.as_view(), name='landing'),

    # Authentication
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.user_logout_view, name='logout'),
    path('register/', views.RegisterOwnerView.as_view(), name='register'),
    path('profile/', views.profile_view, name='profile'),

    # Password Reset Flow (Statutory Secure Reset)
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='public/password_reset.html',
            email_template_name='public/password_reset_email.html',
            subject_template_name='public/password_reset_subject.txt',
            success_url='/password-reset/done/'
        ),
        name='password_reset'
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='public/password_reset_done.html'
        ),
        name='password_reset_done'
    ),
    path(
        'password-reset-confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='public/password_reset_confirm.html',
            success_url='/password-reset-complete/'
        ),
        name='password_reset_confirm'
    ),
    path(
        'password-reset-complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='public/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),
]
