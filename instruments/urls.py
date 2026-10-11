from django.urls import path
from . import views

app_name = 'instruments'

urlpatterns = [
    path('', views.instrument_list_view, name='list'),
    path('add/', views.instrument_create_view, name='add'),
    path('<int:pk>/', views.instrument_detail_view, name='detail'),
    path('<int:pk>/edit/', views.instrument_edit_view, name='edit'),
]
