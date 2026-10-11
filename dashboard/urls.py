from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Role Dispatcher
    path('', views.dashboard_index_view, name='index'),

    # Role Specific Dashboard Shells
    path('owner/', views.owner_dashboard_view, name='owner'),
    path('lmo/', views.lmo_dashboard_view, name='lmo'),
    path('gatc/', views.gatc_dashboard_view, name='gatc'),
    path('admin-control/', views.admin_dashboard_view, name='admin'),
]
