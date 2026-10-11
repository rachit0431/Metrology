from django.urls import path
from . import views

app_name = 'verification'

urlpatterns = [
    path('', views.application_list_view, name='list'),
    path('apply/', views.application_create_view, name='create'),
    path('apply/<int:instrument_id>/', views.application_create_view, name='create_for_instrument'),
    path('<int:pk>/', views.application_detail_view, name='detail'),
    path('<int:pk>/transition/', views.application_transition_view, name='transition'),
    path('<int:pk>/assign-lmo/', views.gatc_assign_lmo_view, name='assign_lmo'),
    path('<int:pk>/inspect/', views.perform_inspection_view, name='inspect'),
    path('inspection/<int:inspection_id>/', views.inspection_detail_view, name='inspection_detail'),
    path('inspection/<int:inspection_id>/unlock/', views.unlock_inspection_view, name='inspection_unlock'),
]
