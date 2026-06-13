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
from evaluations.models import Session
from deliberations.models import Deliberation
from documents.models import DocumentGenere, TypeDocumentGenere
from documents.services import (
    ReleveNotesGenerator,
    ProcesVerbalGenerator,
    AttestationGenerator,
    GrilleNotesGenerator,
)


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
    annee_id = request.GET.get('annee')

    # Si tous les paramètres sont présents dans la query string → générer le PDF
    if all([semestre_id, filiere_id, promotion_id, annee_id]):
        semestre = get_object_or_404(Semestre, pk=semestre_id)
        filiere = get_object_or_404(Filiere, pk=filiere_id)
        promotion = get_object_or_404(Promotion, pk=promotion_id)
        annee = get_object_or_404(AnneeAcademique, pk=annee_id)

        buffer = BytesIO()
        generator = GrilleNotesGenerator(semestre, filiere, promotion, annee, buffer)
        generator.generate()
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="grille_notes_{semestre.code}_{promotion.code}_{annee.code}.pdf"'
        )
        return response

    # Sinon → afficher le formulaire
    context = {
        'semestres': Semestre.objects.filter(active=True).select_related('promotion').order_by('-promotion', 'numero'),
        'filieres': Filiere.objects.filter(active=True).order_by('code'),
        'promotions': Promotion.objects.filter(active=True).select_related('filiere').order_by('filiere', 'ordre'),
        'annees': AnneeAcademique.objects.all().order_by('-annee_debut'),
    }
    if all([semestre_id, filiere_id, promotion_id, annee_id]):
        context['selected'] = {
            'semestre': int(semestre_id),
            'option': int(filiere_id),
            'promotion': int(promotion_id),
            'annee': int(annee_id),
        }
    return render(request, 'documents/grille_notes.html', context)


# ========== RELEVÉ DE NOTES ==========
@login_required
def releve_notes_selection(request):
    """Page de sélection pour générer un relevé de notes PDF"""
    semestre_id = request.GET.get('semestre')
    filiere_id = request.GET.get('option')
    promotion_id = request.GET.get('promotion')
    annee_id = request.GET.get('annee')
    etudiant_id = request.GET.get('etudiant')

    if all([semestre_id, filiere_id, promotion_id, annee_id, etudiant_id]):
        semestre = get_object_or_404(Semestre, pk=semestre_id)
        filiere = get_object_or_404(Filiere, pk=filiere_id)
        promotion = get_object_or_404(Promotion, pk=promotion_id)
        annee = get_object_or_404(AnneeAcademique, pk=annee_id)
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

    inscriptions = Inscription.objects.filter(statut='inscrit').select_related(
        'etudiant', 'classe__promotion', 'annee_academique'
    ).order_by('etudiant__numero_etudiant')

    context = {
        'semestres': Semestre.objects.filter(active=True).select_related('promotion').order_by('-promotion', 'numero'),
        'filieres': Filiere.objects.filter(active=True).order_by('code'),
        'promotions': Promotion.objects.filter(active=True).select_related('filiere').order_by('filiere', 'ordre'),
        'annees': AnneeAcademique.objects.all().order_by('-annee_debut'),
        'etudiants': Student.objects.filter(statut='actif').order_by('numero_etudiant'),
    }
    if all([semestre_id, filiere_id, promotion_id, annee_id, etudiant_id]):
        context['selected'] = {
            'semestre': int(semestre_id), 'option': int(filiere_id),
            'promotion': int(promotion_id), 'annee': int(annee_id), 'etudiant': int(etudiant_id),
        }
    return render(request, 'documents/releve_notes.html', context)
