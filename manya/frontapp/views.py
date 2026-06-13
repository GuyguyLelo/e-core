from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from academics.models import Section, Promotion, AnneeAcademique
from students.models import Student, Inscription
from evaluations.models import Session
from deliberations.models import Deliberation


@login_required
def projets_tutores_realises(request):
    """Page plein écran - Projets tutorés réalisés"""
    return render(request, 'frontapp/projets_tutores.html')


@login_required
def home(request):
    """Dashboard principal"""
    context = {
        'total_etudiants': Student.objects.count(),
        'total_inscriptions': Inscription.objects.filter(statut='inscrit').count(),
        'total_promotions': Promotion.objects.filter(active=True).count(),
        'total_sections': Section.objects.filter(active=True).count(),
        'annee_active': AnneeAcademique.objects.filter(active=True).first(),
        'sessions_actives': Session.objects.filter(active=True, deliberation_faite=False).count(),
        'deliberations_recentes': Deliberation.objects.filter(statut='terminee').order_by('-date_deliberation')[:5],
    }
    return render(request, 'frontapp/dashboard.html', context)
