from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from academics.models import Section, Promotion, AnneeAcademique
from students.models import Student, Inscription
from evaluations.models import Session
from deliberations.models import Deliberation


def _dashboard_context():
    return {
        'total_etudiants': Student.objects.count(),
        'total_inscriptions': Inscription.objects.filter(statut='inscrit').count(),
        'total_promotions': Promotion.objects.filter(active=True).count(),
        'total_sections': Section.objects.filter(active=True).count(),
        'annee_active': AnneeAcademique.get_active(),
        'sessions_actives': Session.objects.filter(active=True, deliberation_faite=False).count(),
        'deliberations_recentes': Deliberation.objects.filter(statut='terminee').order_by('-date_deliberation')[:5],
    }


@login_required
def accueil(request):
    """Page d'accueil — sélection des fonctionnalités."""
    return render(request, 'frontapp/accueil.html')


@login_required
def dashboard(request):
    """Tableau de bord — statistiques et indicateurs."""
    return render(request, 'frontapp/dashboard.html', _dashboard_context())


@login_required
def home(request):
    """Alias post-connexion vers l'accueil."""
    return accueil(request)


@login_required
def projets_tutores_realises(request):
    """Page plein écran - Projets tutorés réalisés"""
    return render(request, 'frontapp/projets_tutores.html')
