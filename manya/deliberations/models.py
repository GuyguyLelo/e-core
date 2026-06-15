"""
Modèles pour les délibérations : Délibération, Décision, Paramètres LMD
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from academics.models import Semestre, Promotion
from students.models import Inscription, Student
from evaluations.models import Session
from decimal import Decimal


class ParametresLMD(models.Model):
    """Paramètres de configuration LMD (seuils, compensation, etc.)"""
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='parametres_lmd', verbose_name="Promotion")
    seuil_validation = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Seuil de validation (/20)"
    )
    compensation_intra_ue = models.BooleanField(default=True, verbose_name="Compensation intra-UE")
    compensation_intra_semestre = models.BooleanField(default=True, verbose_name="Compensation intra-semestre")
    compensation_annuelle = models.BooleanField(default=True, verbose_name="Compensation annuelle")
    capitalisation_ue = models.BooleanField(default=True, verbose_name="Capitalisation des UE")
    capitalisation_ec = models.BooleanField(default=True, verbose_name="Capitalisation des EC")
    passage_avec_dettes = models.BooleanField(default=True, verbose_name="Passage avec dettes")
    seuil_credits_minimum = models.IntegerField(default=30, validators=[MinValueValidator(0)], verbose_name="Seuil crédits minimum pour passage")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètres LMD"
        verbose_name_plural = "Paramètres LMD"
        unique_together = [['promotion']]

    def __str__(self):
        return f"Paramètres LMD - {self.promotion.code}"


class Deliberation(models.Model):
    """Délibération d'un jury pour une session et une promotion"""
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='deliberations', verbose_name="Session")
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='deliberations', verbose_name="Promotion")
    date_deliberation = models.DateField(verbose_name="Date de délibération")
    president_jury = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliberations_president', verbose_name="Président du jury")
    membres_jury = models.ManyToManyField(User, related_name='deliberations_membre', blank=True, verbose_name="Membres du jury")
    statut = models.CharField(
        max_length=20,
        choices=[
            ('en_preparation', 'En préparation'),
            ('en_cours', 'En cours'),
            ('terminee', 'Terminée'),
            ('verrouillee', 'Verrouillée'),
        ],
        default='en_preparation',
        verbose_name="Statut"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Notes du jury")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Délibération"
        verbose_name_plural = "Délibérations"
        unique_together = [['session', 'promotion']]
        ordering = ['-date_deliberation']

    def __str__(self):
        return f"Délibération - {self.session.code} ({self.date_deliberation})"


class DecisionJury(models.Model):
    """Décision du jury pour un étudiant lors d'une délibération"""
    deliberation = models.ForeignKey(Deliberation, on_delete=models.CASCADE, related_name='decisions', verbose_name="Délibération")
    etudiant = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='decisions_jury', verbose_name="Étudiant")
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name='decisions_jury', verbose_name="Inscription")
    decision = models.CharField(
        max_length=20,
        choices=[
            ('admis', 'Admis'),
            ('admis_avec_dettes', 'Admis avec dettes'),
            ('redouble', 'Redouble'),
            ('exclu', 'Exclu'),
            ('ajourne', 'Ajourné'),
            ('report', 'Report'),
        ],
        verbose_name="Décision"
    )
    moyenne_semestre = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Moyenne du semestre"
    )
    credits_obtenus = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Crédits obtenus"
    )
    credits_totaux = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('30.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Crédits totaux"
    )
    rang = models.IntegerField(null=True, blank=True, verbose_name="Rang")
    mention = models.CharField(
        max_length=20,
        choices=[
            ('', 'Sans mention'),
            ('passable', 'Passable'),
            ('assez_bien', 'Assez Bien'),
            ('bien', 'Bien'),
            ('tres_bien', 'Très Bien'),
        ],
        blank=True,
        verbose_name="Mention"
    )
    notes_jury = models.TextField(blank=True, null=True, verbose_name="Notes du jury")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Décision du jury"
        verbose_name_plural = "Décisions du jury"
        unique_together = [['deliberation', 'etudiant']]
        ordering = ['deliberation', 'rang', 'etudiant']

    def __str__(self):
        return f"{self.etudiant.numero_etudiant} - {self.decision} ({self.deliberation.session.code})"
