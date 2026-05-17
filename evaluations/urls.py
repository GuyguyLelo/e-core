from django.urls import path
from .views import *

app_name = 'evaluations'

urlpatterns = [
    # Types d'évaluation
    path('types-evaluation/', type_evaluation_list, name='type_evaluation_list'),
    path('types-evaluation/nouveau/', type_evaluation_create, name='type_evaluation_create'),
    path('types-evaluation/<int:pk>/modifier/', type_evaluation_update, name='type_evaluation_update'),
    path('types-evaluation/<int:pk>/supprimer/', type_evaluation_delete, name='type_evaluation_delete'),
    
    # Sessions
    path('sessions/', session_list, name='session_list'),
    path('sessions/nouvelle/', session_create, name='session_create'),
    path('sessions/<int:pk>/modifier/', session_update, name='session_update'),
    path('sessions/<int:pk>/supprimer/', session_delete, name='session_delete'),
    
    # Évaluations
    path('evaluations/', evaluation_list, name='evaluation_list'),
    path('evaluations/nouvelle/', evaluation_create, name='evaluation_create'),
    path('evaluations/<int:pk>/modifier/', evaluation_update, name='evaluation_update'),
    path('evaluations/<int:pk>/supprimer/', evaluation_delete, name='evaluation_delete'),
    path('evaluations/<int:evaluation_id>/saisie-masse/', saisie_masse_notes, name='saisie_masse_notes'),
    
    # Notes
    path('notes/', note_list, name='note_list'),
    path('notes/nouvelle/', note_create, name='note_create'),
    path('notes/<int:pk>/modifier/', note_update, name='note_update'),
    path('notes/<int:pk>/supprimer/', note_delete, name='note_delete'),
]
