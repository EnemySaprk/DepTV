from django.urls import path
from . import views

app_name = 'canales'

urlpatterns = [
    path('', views.home, name='home'),
    path('video/<int:pk>/', views.detalle_video, name='detalle_video'),
    path('canal/<slug:slug>/', views.lista_canal, name='canal'),
    path('liga/<slug:slug>/', views.lista_liga, name='liga'),
    path('agenda/', views.agenda, name='agenda'),
]
