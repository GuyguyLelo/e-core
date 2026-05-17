"""
Vues pour l'application deliberations
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import ParametresLMD, Deliberation, DecisionJury
from .forms import ParametresLMDForm, DeliberationForm, DecisionJuryForm
from .services import DeliberationEngine
from evaluations.models import Session
from students.models import Inscription


# ========== PARAMETRES LMD ==========
@login_required
def parametres_lmd_list(request):
    parametres = ParametresLMD.objects.select_related('promotion').all()
    return render(request, 'deliberations/parametres_lmd_list.html', {'parametres': parametres})


@login_required
def parametres_lmd_create(request):
    if request.method == 'POST':
        form = ParametresLMDForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paramètres LMD créés avec succès!')
            return redirect('deliberations:parametres_lmd_list')
    else:
        form = ParametresLMDForm()
    return render(request, 'deliberations/parametres_lmd_form.html', {'form': form, 'title': 'Nouveaux Paramètres LMD'})


@login_required
def parametres_lmd_update(request, pk):
    parametres = get_object_or_404(ParametresLMD, pk=pk)
    if request.method == 'POST':
        form = ParametresLMDForm(request.POST, instance=parametres)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paramètres LMD modifiés avec succès!')
            return redirect('deliberations:parametres_lmd_list')
    else:
        form = ParametresLMDForm(instance=parametres)
    return render(request, 'deliberations/parametres_lmd_form.html', {'form': form, 'title': 'Modifier Paramètres LMD', 'object': parametres})


# ========== DELIBERATIONS ==========
@login_required
def deliberation_list(request):
    deliberations = Deliberation.objects.select_related('session', 'president_jury').all().order_by('-date_deliberation')
    paginator = Paginator(deliberations, 10)
    page = request.GET.get('page')
    deliberations = paginator.get_page(page)
    return render(request, 'deliberations/deliberation_list.html', {'deliberations': deliberations})


@login_required
def deliberation_create(request):
    if request.method == 'POST':
        form = DeliberationForm(request.POST)
        if form.is_valid():
            deliberation = form.save(commit=False)
            if not deliberation.president_jury:
                deliberation.president_jury = request.user
            deliberation.save()
            form.save_m2m()  # Pour les membres du jury
            messages.success(request, 'Délibération créée avec succès!')
            return redirect('deliberations:deliberation_list')
    else:
        form = DeliberationForm()
    return render(request, 'deliberations/deliberation_form.html', {'form': form, 'title': 'Nouvelle Délibération'})


@login_required
def deliberation_update(request, pk):
    deliberation = get_object_or_404(Deliberation, pk=pk)
    if request.method == 'POST':
        form = DeliberationForm(request.POST, instance=deliberation)
        if form.is_valid():
            form.save()
            messages.success(request, 'Délibération modifiée avec succès!')
            return redirect('deliberations:deliberation_list')
    else:
        form = DeliberationForm(instance=deliberation)
    return render(request, 'deliberations/deliberation_form.html', {'form': form, 'title': 'Modifier Délibération', 'object': deliberation})


@login_required
def deliberation_detail(request, pk):
    deliberation = get_object_or_404(Deliberation, pk=pk)
    decisions = DecisionJury.objects.filter(deliberation=deliberation).order_by('rang', 'etudiant')
    return render(request, 'deliberations/deliberation_detail.html', {
        'deliberation': deliberation,
        'decisions': decisions
    })


@login_required
def deliberation_calculer(request, pk):
    """Calcule les notes et décisions pour une délibération"""
    deliberation = get_object_or_404(Deliberation, pk=pk)
    session = deliberation.session
    
    if request.method == 'POST':
        # Utiliser le moteur de délibération
        engine = DeliberationEngine(session)
        resultats = engine.traiter_tous_etudiants()
        
        # Créer les décisions du jury
        decisions_crees = 0
        for resultat in resultats:
            etudiant = resultat['etudiant']
            inscription = Inscription.objects.filter(
                etudiant=etudiant,
                classe__promotion=session.semestre.promotion,
                statut='inscrit'
            ).select_related('classe').first()
            
            if inscription:
                decision, created = DecisionJury.objects.update_or_create(
                    deliberation=deliberation,
                    etudiant=etudiant,
                    defaults={
                        'inscription': inscription,
                        'moyenne_semestre': resultat['moyenne_semestre'],
                        'credits_obtenus': resultat['credits_obtenus'],
                        'credits_totaux': resultat['credits_totaux'],
                        'decision': resultat['decision'],
                    }
                )
                if created:
                    decisions_crees += 1
        
        messages.success(request, f'Calculs effectués avec succès! {decisions_crees} décisions créées.')
        return redirect('deliberations:deliberation_detail', pk=deliberation.pk)
    
    return render(request, 'deliberations/deliberation_calculer.html', {'deliberation': deliberation})


# ========== DECISIONS JURY ==========
@login_required
def decision_jury_update(request, pk):
    decision = get_object_or_404(DecisionJury, pk=pk)
    if request.method == 'POST':
        form = DecisionJuryForm(request.POST, instance=decision)
        if form.is_valid():
            form.save()
            messages.success(request, 'Décision modifiée avec succès!')
            return redirect('deliberations:deliberation_detail', pk=decision.deliberation.pk)
    else:
        form = DecisionJuryForm(instance=decision)
    return render(request, 'deliberations/decision_jury_form.html', {'form': form, 'title': 'Modifier Décision', 'object': decision})
