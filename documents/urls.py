from django.urls import path
from .views import *

app_name = 'documents'

urlpatterns = [
    path('releve-notes/<int:etudiant_id>/<int:session_id>/', generate_releve_notes, name='generate_releve_notes'),
    path('proces-verbal/<int:deliberation_id>/', generate_proces_verbal, name='generate_proces_verbal'),
    path('attestation/<int:inscription_id>/<str:type_attestation>/', generate_attestation, name='generate_attestation'),
]
