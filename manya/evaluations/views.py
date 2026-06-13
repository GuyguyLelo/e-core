"""
Vues pour l'application evaluations
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from decimal import Decimal
from .models import TypeEvaluation, Session, Evaluation, Note
from students.models import Inscription, Student
from academics.models import ElementConstitutif
from .forms import TypeEvaluationForm, SessionForm, EvaluationForm, NoteForm


# ========== TYPES D'EVALUATION ==========
@login_required
def type_evaluation_list(request):
    types = TypeEvaluation.objects.all().order_by('ordre', 'nom')
    return render(request, 'evaluations/type_evaluation_list.html', {'types': types})


@login_required
def type_evaluation_create(request):
    if request.method == 'POST':
        form = TypeEvaluationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Type d\'évaluation créé avec succès!')
            return redirect('evaluations:type_evaluation_list')
    else:
        form = TypeEvaluationForm()
    return render(request, 'evaluations/type_evaluation_form.html', {'form': form, 'title': 'Nouveau Type d\'Évaluation'})


@login_required
def type_evaluation_update(request, pk):
    type_eval = get_object_or_404(TypeEvaluation, pk=pk)
    if request.method == 'POST':
        form = TypeEvaluationForm(request.POST, instance=type_eval)
        if form.is_valid():
            form.save()
            messages.success(request, 'Type d\'évaluation modifié avec succès!')
            return redirect('evaluations:type_evaluation_list')
    else:
        form = TypeEvaluationForm(instance=type_eval)
    return render(request, 'evaluations/type_evaluation_form.html', {'form': form, 'title': 'Modifier Type d\'Évaluation', 'object': type_eval})


@login_required
def type_evaluation_delete(request, pk):
    type_eval = get_object_or_404(TypeEvaluation, pk=pk)
    if request.method == 'POST':
        type_eval.delete()
        messages.success(request, 'Type d\'évaluation supprimé avec succès!')
        return redirect('evaluations:type_evaluation_list')
    return render(request, 'evaluations/type_evaluation_confirm_delete.html', {'type_eval': type_eval})


# ========== SESSIONS ==========
@login_required
def session_list(request):
    sessions = Session.objects.select_related('semestre').all().order_by('-semestre', 'numero')
    paginator = Paginator(sessions, 10)
    page = request.GET.get('page')
    sessions = paginator.get_page(page)
    return render(request, 'evaluations/session_list.html', {'sessions': sessions})


@login_required
def session_create(request):
    if request.method == 'POST':
        form = SessionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Session créée avec succès!')
            return redirect('evaluations:session_list')
    else:
        form = SessionForm()
    return render(request, 'evaluations/session_form.html', {'form': form, 'title': 'Nouvelle Session'})


@login_required
def session_update(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, 'Session modifiée avec succès!')
            return redirect('evaluations:session_list')
    else:
        form = SessionForm(instance=session)
    return render(request, 'evaluations/session_form.html', {'form': form, 'title': 'Modifier Session', 'object': session})


@login_required
def session_delete(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        session.delete()
        messages.success(request, 'Session supprimée avec succès!')
        return redirect('evaluations:session_list')
    return render(request, 'evaluations/session_confirm_delete.html', {'session': session})


# ========== EVALUATIONS ==========
@login_required
def evaluation_list(request):
    evaluations = Evaluation.objects.select_related('ec', 'session', 'type_evaluation').all().order_by('session', 'ec')
    paginator = Paginator(evaluations, 15)
    page = request.GET.get('page')
    evaluations = paginator.get_page(page)
    return render(request, 'evaluations/evaluation_list.html', {'evaluations': evaluations})


@login_required
def evaluation_create(request):
    if request.method == 'POST':
        form = EvaluationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Évaluation créée avec succès!')
            return redirect('evaluations:evaluation_list')
    else:
        form = EvaluationForm()
    return render(request, 'evaluations/evaluation_form.html', {'form': form, 'title': 'Nouvelle Évaluation'})


@login_required
def evaluation_update(request, pk):
    evaluation = get_object_or_404(Evaluation, pk=pk)
    if request.method == 'POST':
        form = EvaluationForm(request.POST, instance=evaluation)
        if form.is_valid():
            form.save()
            messages.success(request, 'Évaluation modifiée avec succès!')
            return redirect('evaluations:evaluation_list')
    else:
        form = EvaluationForm(instance=evaluation)
    return render(request, 'evaluations/evaluation_form.html', {'form': form, 'title': 'Modifier Évaluation', 'object': evaluation})


@login_required
def evaluation_delete(request, pk):
    evaluation = get_object_or_404(Evaluation, pk=pk)
    if request.method == 'POST':
        evaluation.delete()
        messages.success(request, 'Évaluation supprimée avec succès!')
        return redirect('evaluations:evaluation_list')
    return render(request, 'evaluations/evaluation_confirm_delete.html', {'evaluation': evaluation})


# ========== NOTES ==========
@login_required
def note_list(request):
    notes = Note.objects.select_related('etudiant', 'evaluation').all().order_by('evaluation__id', 'etudiant__numero_etudiant')
    paginator = Paginator(notes, 20)
    page = request.GET.get('page')
    notes = paginator.get_page(page)
    return render(request, 'evaluations/note_list.html', {'notes': notes})


@login_required
def note_create(request):
    if request.method == 'POST':
        form = NoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.saisie_par = request.user
            note.save()
            messages.success(request, 'Note saisie avec succès!')
            return redirect('evaluations:note_list')
    else:
        form = NoteForm()
    return render(request, 'evaluations/note_form.html', {'form': form, 'title': 'Nouvelle Note'})


@login_required
def note_update(request, pk):
    note = get_object_or_404(Note, pk=pk)
    if request.method == 'POST':
        form = NoteForm(request.POST, instance=note)
        if form.is_valid():
            note_obj = form.save(commit=False)
            note_obj.modifie_par = request.user
            note_obj.save()
            messages.success(request, 'Note modifiée avec succès!')
            return redirect('evaluations:note_list')
    else:
        form = NoteForm(instance=note)
    return render(request, 'evaluations/note_form.html', {'form': form, 'title': 'Modifier Note', 'object': note})


@login_required
def note_delete(request, pk):
    note = get_object_or_404(Note, pk=pk)
    if request.method == 'POST':
        note.delete()
        messages.success(request, 'Note supprimée avec succès!')
        return redirect('evaluations:note_list')
    return render(request, 'evaluations/note_confirm_delete.html', {'note': note})


# ========== SAISIE MASSE DES NOTES ==========
@login_required
def saisie_masse_notes(request, evaluation_id):
    """Saisie de notes pour tous les étudiants d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id)
    # Récupérer les étudiants inscrits dans la promotion du semestre
    semestre = evaluation.session.semestre
    inscriptions = Inscription.objects.filter(
        classe__promotion=semestre.promotion,
        statut='inscrit'
    ).select_related('etudiant', 'classe')
    
    if request.method == 'POST':
        # Traiter la saisie en masse
        for inscription in inscriptions:
            etudiant = inscription.etudiant
            note_value = request.POST.get(f'note_{etudiant.id}')
            note_sur_value = request.POST.get(f'note_sur_{etudiant.id}')
            absent = request.POST.get(f'absent_{etudiant.id}') == 'on'
            justifie = request.POST.get(f'justifie_{etudiant.id}') == 'on'
            
            if note_value or absent:
                note, created = Note.objects.get_or_create(
                    etudiant=etudiant,
                    evaluation=evaluation,
                    defaults={'saisie_par': request.user}
                )
                if absent:
                    note.absent = True
                    note.note = None
                    note.justifie = justifie
                else:
                    note.absent = False
                    note.note = Decimal(note_value) if note_value else None
                    note.justifie = False
                
                if note_sur_value:
                    note.note_sur = Decimal(note_sur_value)
                
                note.save()
        
        messages.success(request, 'Notes saisies avec succès!')
        return redirect('evaluations:evaluation_list')
    
    # Préparer les données pour l'affichage
    etudiants_notes = []
    for inscription in inscriptions:
        etudiant = inscription.etudiant
        note = Note.objects.filter(etudiant=etudiant, evaluation=evaluation).first()
        etudiants_notes.append({
            'etudiant': etudiant,
            'note': note
        })
    
    return render(request, 'evaluations/saisie_masse_notes.html', {
        'evaluation': evaluation,
        'etudiants_notes': etudiants_notes
    })


# ========== NOTE PAR ÉTUDIANT ==========
@login_required
def note_par_etudiant(request):
    """Saisie de notes par étudiant : affiche toutes les évaluations d'un étudiant pour une session"""
    etudiant = None
    session = None
    evaluations_notes = []

    if request.method == 'POST':
        etudiant_id = request.POST.get('etudiant')
        session_id = request.POST.get('session')

        if etudiant_id and session_id:
            etudiant = get_object_or_404(Student, pk=etudiant_id)
            session = get_object_or_404(Session, pk=session_id)

            # Récupérer les ECs du semestre de la session
            ecs = ElementConstitutif.objects.filter(
                ue__semestre=session.semestre,
                active=True
            ).select_related('ue').order_by('ue__ordre', 'ordre', 'code')

            # Récupérer les évaluations
            evaluations = Evaluation.objects.filter(
                ec__in=ecs,
                session=session,
                active=True
            ).select_related('ec', 'type_evaluation').order_by('ec', 'type_evaluation')

            for evaluation in evaluations:
                note = Note.objects.filter(etudiant=etudiant, evaluation=evaluation).first()
                evaluations_notes.append({
                    'evaluation': evaluation,
                    'note': note,
                })

            # Si c'est une soumission de notes (bouton "Enregistrer")
            if 'enregistrer_notes' in request.POST:
                for evaluation in evaluations:
                    note_value = request.POST.get(f'note_{evaluation.id}')
                    note_sur_value = request.POST.get(f'note_sur_{evaluation.id}')
                    absent = request.POST.get(f'absent_{evaluation.id}') == 'on'
                    justifie = request.POST.get(f'justifie_{evaluation.id}') == 'on'

                    if note_value or absent:
                        note_obj, created = Note.objects.get_or_create(
                            etudiant=etudiant,
                            evaluation=evaluation,
                            defaults={'saisie_par': request.user}
                        )
                        if absent:
                            note_obj.absent = True
                            note_obj.note = None
                            note_obj.justifie = justifie
                        else:
                            note_obj.absent = False
                            note_obj.note = Decimal(note_value) if note_value else None
                            note_obj.justifie = False

                        if note_sur_value:
                            note_obj.note_sur = Decimal(note_sur_value)

                        note_obj.modifie_par = request.user
                        note_obj.save()

                messages.success(request, f'Notes enregistrées pour {etudiant.nom_complet}')
                return redirect('evaluations:note_par_etudiant')

    etudiants = Student.objects.filter(statut='actif').order_by('numero_etudiant')
    sessions = Session.objects.filter(active=True).select_related('semestre').order_by('-semestre__promotion', '-numero')

    return render(request, 'evaluations/note_par_etudiant.html', {
        'etudiant': etudiant,
        'session': session,
        'evaluations_notes': evaluations_notes,
        'etudiants': etudiants,
        'sessions': sessions,
    })


# ========== NOTE PAR EC ==========
@login_required
def note_par_ec(request):
    """Saisie de notes par EC : affiche tous les étudiants d'un EC pour une session"""
    ec_selected = None
    session = None
    etudiants_notes = []

    if request.method == 'POST':
        ec_id = request.POST.get('ec')
        session_id = request.POST.get('session')

        if ec_id and session_id:
            ec_selected = get_object_or_404(ElementConstitutif, pk=ec_id)
            session = get_object_or_404(Session, pk=session_id)

            # Récupérer les inscriptions de la promotion du semestre
            inscriptions = Inscription.objects.filter(
                classe__promotion=session.semestre.promotion,
                statut='inscrit'
            ).select_related('etudiant', 'classe').order_by('etudiant__numero_etudiant')

            # Récupérer les évaluations pour cet EC dans cette session
            evaluations = Evaluation.objects.filter(
                ec=ec_selected,
                session=session,
                active=True
            ).select_related('type_evaluation').order_by('type_evaluation')

            for inscription in inscriptions:
                etudiant = inscription.etudiant
                notes_eval = []
                for evaluation in evaluations:
                    note = Note.objects.filter(etudiant=etudiant, evaluation=evaluation).first()
                    notes_eval.append({
                        'evaluation': evaluation,
                        'note': note,
                    })
                etudiants_notes.append({
                    'etudiant': etudiant,
                    'classe': inscription.classe,
                    'notes_eval': notes_eval,
                })

            # Si c'est une soumission de notes (bouton "Enregistrer")
            if 'enregistrer_notes' in request.POST:
                for inscription in inscriptions:
                    etudiant = inscription.etudiant
                    for evaluation in evaluations:
                        note_value = request.POST.get(f'note_{etudiant.id}_{evaluation.id}')
                        note_sur_value = request.POST.get(f'note_sur_{etudiant.id}_{evaluation.id}')
                        absent = request.POST.get(f'absent_{etudiant.id}_{evaluation.id}') == 'on'
                        justifie = request.POST.get(f'justifie_{etudiant.id}_{evaluation.id}') == 'on'

                        if note_value or absent:
                            note_obj, created = Note.objects.get_or_create(
                                etudiant=etudiant,
                                evaluation=evaluation,
                                defaults={'saisie_par': request.user}
                            )
                            if absent:
                                note_obj.absent = True
                                note_obj.note = None
                                note_obj.justifie = justifie
                            else:
                                note_obj.absent = False
                                note_obj.note = Decimal(note_value) if note_value else None
                                note_obj.justifie = False

                            if note_sur_value:
                                note_obj.note_sur = Decimal(note_sur_value)

                            note_obj.modifie_par = request.user
                            note_obj.save()

                messages.success(request, f'Notes enregistrées pour {ec_selected.code}')
                return redirect('evaluations:note_par_ec')

    ecs = ElementConstitutif.objects.filter(active=True).select_related('ue').order_by('ue__semestre', 'ue', 'ordre')
    sessions = Session.objects.filter(active=True).select_related('semestre').order_by('-semestre__promotion', '-numero')

    return render(request, 'evaluations/note_par_ec.html', {
        'ec_selected': ec_selected,
        'session': session,
        'etudiants_notes': etudiants_notes,
        'ecs': ecs,
        'sessions': sessions,
    })
