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
from evaluations.models import Session
from deliberations.models import Deliberation
from documents.models import DocumentGenere, TypeDocumentGenere
from documents.services import (
    ReleveNotesGenerator,
    ProcesVerbalGenerator,
    AttestationGenerator
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
