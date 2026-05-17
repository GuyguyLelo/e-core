from django.urls import path
from .views import *

urlpatterns = [
    path('', home, name='home'),
    path('dashboard/', home, name='dashboard'),
    path('projets-tutores-realises/', projets_tutores_realises, name='projets_tutores_realises'),
]
