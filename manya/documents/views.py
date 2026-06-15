"""
Vues pour la génération de documents
"""
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from io import BytesIO

from students.models import Student, Inscription
from academics.models import Semestre, Filiere, Promotion, AnneeAcademique
from academics.utils import NO_ACTIVE_ANNEE_ERROR
from evaluations.models import Session
from deliberations.models import Deliberation
from documents.models import DocumentGenere, TypeDocumentGenere
from documents.services import (
    ReleveNotesGenerator,
    ProcesVerbalGenerator,
    AttestationGenerator,
    GrilleNotesGenerator,
)


def _document_selection_from_get(request, include_etudiant=False):
    """Extrait les sélections du formulaire GET pour pré-remplir les listes."""
    selected = {}
    mapping = {
        'semestre': request.GET.get('semestre'),
        'option': request.GET.get('option'),
        'promotion': request.GET.get('promotion'),
    }
    if include_etudiant:
        mapping['etudiant'] = request.GET.get('etudiant')
    for key, value in mapping.items():
        if value and value.isdigit():
            selected[key] = int(value)
    return selected


@login_required
def generate_releve_notes(request, etudiant_id, session_id):
    """Génère un relevé de notes pour un étudiant"""
    etudiant = get_object_or_404(Student, id=etudiant_id)
    session = get_object_or_404(Session, id=session_id)
    
    # Générer le PDF
    buffer = BytesIO()
    generator = ReleveNotesGenerator(etudiant, session, buffer)
    generator.generate()
    
    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="releve_notes_{etudiant.numero_etudiant}_{session.code}.pdf"'
    
    # Sauvegarder le document généré
    type_doc, created = TypeDocumentGenere.objects.get_or_create(
        code='RELEVE_NOTES',
        defaults={'nom': 'Relevé de notes', 'active': True}
    )
    
    DocumentGenere.objects.create(
        type_document=type_doc,
        etudiant=etudiant,
        session=session,
        fichier=f'releve_notes_{etudiant.numero_etudiant}_{session.code}.pdf',
        genere_par=request.user
    )
    
    return response


@login_required
def generate_proces_verbal(request, deliberation_id):
    """Génère un procès-verbal de délibération"""
    deliberation = get_object_or_404(Deliberation, id=deliberation_id)
    
    # Générer le PDF
    buffer = BytesIO()
    generator = ProcesVerbalGenerator(deliberation, buffer)
    generator.generate()
    
    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="proces_verbal_{deliberation.session.code}.pdf"'
    
    # Sauvegarder le document généré
    type_doc, created = TypeDocumentGenere.objects.get_or_create(
        code='PROCES_VERBAL',
        defaults={'nom': 'Procès-verbal de délibération', 'active': True}
    )
    
    DocumentGenere.objects.create(
        type_document=type_doc,
        deliberation=deliberation,
        session=deliberation.session,
        fichier=f'proces_verbal_{deliberation.session.code}.pdf',
        genere_par=request.user
    )
    
    return response


@login_required
def generate_attestation(request, inscription_id, type_attestation='scolarite'):
    """Génère une attestation"""
    inscription = get_object_or_404(Inscription, id=inscription_id)
    etudiant = inscription.etudiant
    
    # Générer le PDF
    buffer = BytesIO()
    generator = AttestationGenerator(etudiant, inscription, type_attestation, buffer)
    generator.generate()
    
    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="attestation_{etudiant.numero_etudiant}.pdf"'
    
    # Sauvegarder le document généré
    type_doc, created = TypeDocumentGenere.objects.get_or_create(
        code=f'ATTESTATION_{type_attestation.upper()}',
        defaults={'nom': f'Attestation de {type_attestation}', 'active': True}
    )
    
    DocumentGenere.objects.create(
        type_document=type_doc,
        etudiant=etudiant,
        inscription=inscription,
        fichier=f'attestation_{etudiant.numero_etudiant}.pdf',
        genere_par=request.user
    )

    return response


# ========== GRILLE DE NOTES ==========
@login_required
def grille_notes(request):
    """
    Page de sélection des paramètres pour générer la grille de notes PDF.
    Si les paramètres sont déjà dans la query string, génère et renvoie le PDF directement.
    """
    semestre_id = request.GET.get('semestre')
    filiere_id = request.GET.get('option')
    promotion_id = request.GET.get('promotion')

    if all([semestre_id, filiere_id, promotion_id]):
        annee = AnneeAcademique.get_active()
        if not annee:
            messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        else:
            semestre = get_object_or_404(Semestre, pk=semestre_id)
            filiere = get_object_or_404(Filiere, pk=filiere_id)
            promotion = get_object_or_404(Promotion, pk=promotion_id)

            buffer = BytesIO()
            generator = GrilleNotesGenerator(semestre, filiere, promotion, annee, buffer)
            generator.generate()
            buffer.seek(0)
            response = HttpResponse(buffer.read(), content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="grille_notes_{semestre.code}_{promotion.code}_{annee.code}.pdf"'
            )
            return response

    context = {
        'semestres': Semestre.objects.filter(active=True).order_by('numero'),
        'filieres': Filiere.objects.filter(active=True).order_by('code'),
        'promotions': Promotion.objects.filter(active=True).select_related('filiere').order_by('filiere', 'ordre'),
        'selected': _document_selection_from_get(request),
    }
    return render(request, 'documents/grille_notes.html', context)


# ========== RELEVÉ DE NOTES ==========
def _inscriptions_pour_releve(promotion_id, filiere_id=None):
    """Inscriptions actives de la promotion pour l'année académique en cours."""
    annee = AnneeAcademique.get_active()
    if not annee or not promotion_id:
        return Inscription.objects.none(), annee

    qs = (
        Inscription.objects.filter(
            annee_academique=annee,
            classe__promotion_id=promotion_id,
        )
        .exclude(statut='desinscrit')
        .select_related('etudiant', 'classe', 'classe__promotion', 'classe__promotion__filiere')
        .order_by('etudiant__numero_etudiant')
    )
    if filiere_id:
        qs = qs.filter(classe__promotion__filiere_id=filiere_id)
    return qs, annee


@login_required
def releve_notes_selection(request):
    """Page de sélection pour générer un relevé de notes PDF"""
    semestre_id = request.GET.get('semestre')
    filiere_id = request.GET.get('option')
    promotion_id = request.GET.get('promotion')
    etudiant_id = request.GET.get('etudiant')

    if all([semestre_id, filiere_id, promotion_id, etudiant_id]):
        annee = AnneeAcademique.get_active()
        if not annee:
            messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        else:
            semestre = get_object_or_404(Semestre, pk=semestre_id)
            filiere = get_object_or_404(Filiere, pk=filiere_id)
            promotion = get_object_or_404(Promotion, pk=promotion_id)
            etudiant = get_object_or_404(Student, pk=etudiant_id)

            buffer = BytesIO()
            generator = ReleveNotesGenerator(etudiant, semestre, filiere, promotion, annee, buffer)
            generator.generate()
            buffer.seek(0)
            response = HttpResponse(buffer.read(), content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="releve_notes_{etudiant.numero_etudiant}_{semestre.code}.pdf"'
            )
            return response

    selected = _document_selection_from_get(request, include_etudiant=True)
    inscriptions_promotion = Inscription.objects.none()
    if selected.get('promotion'):
        filiere_pk = selected.get('option')
        inscriptions_promotion, _ = _inscriptions_pour_releve(
            selected['promotion'],
            filiere_pk,
        )

    context = {
        'semestres': Semestre.objects.filter(active=True).order_by('numero'),
        'filieres': Filiere.objects.filter(active=True).order_by('code'),
        'promotions': Promotion.objects.filter(active=True).select_related('filiere').order_by('filiere', 'ordre'),
        'inscriptions_promotion': inscriptions_promotion,
        'selected': selected,
    }
    return render(request, 'documents/releve_notes.html', context)
