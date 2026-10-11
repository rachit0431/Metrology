from django.urls import path
from . import views

app_name = 'certificates'

urlpatterns = [
    path('', views.certificate_list_view, name='list'),
    path('generate/<int:application_id>/', views.generate_certificate_view, name='generate'),
    path('<str:certificate_number>/revoke/', views.revoke_certificate_view, name='revoke'),
    path('<str:certificate_number>/', views.certificate_detail_view, name='detail'),
]
