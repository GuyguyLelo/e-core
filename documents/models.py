"""
Modèles pour la gestion des documents générés
"""
from django.db import models
from django.contrib.auth.models import User
from students.models import Student, Inscription
from evaluations.models import Session
from deliberations.models import Deliberation
import os


def document_generated_path(instance, filename):
    """Génère le chemin pour les documents générés"""
    return f'documents/generated/{instance.type_document}/{instance.etudiant.numero_etudiant if instance.etudiant else "deliberation"}/{filename}'


class TypeDocumentGenere(models.Model):
    """Types de documents générables"""
    code = models.CharField(max_length=20, unique=True, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    template_pdf = models.CharField(max_length=200, blank=True, null=True, verbose_name="Template PDF")
    active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Type de document généré"
        verbose_name_plural = "Types de documents générés"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class DocumentGenere(models.Model):
    """Document PDF généré"""
    type_document = models.ForeignKey(TypeDocumentGenere, on_delete=models.CASCADE, related_name='documents', verbose_name="Type de document")
    etudiant = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='documents_generes', null=True, blank=True, verbose_name="Étudiant")
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name='documents_generes', null=True, blank=True, verbose_name="Inscription")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='documents_generes', null=True, blank=True, verbose_name="Session")
    deliberation = models.ForeignKey(Deliberation, on_delete=models.CASCADE, related_name='documents_generes', null=True, blank=True, verbose_name="Délibération")
    fichier = models.FileField(upload_to=document_generated_path, verbose_name="Fichier PDF")
    date_generation = models.DateTimeField(auto_now_add=True, verbose_name="Date de génération")
    genere_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Généré par")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Document généré"
        verbose_name_plural = "Documents générés"
        ordering = ['-date_generation']

    def __str__(self):
        if self.etudiant:
            return f"{self.type_document.nom} - {self.etudiant.numero_etudiant}"
        return f"{self.type_document.nom} - {self.date_generation.strftime('%Y-%m-%d')}"
