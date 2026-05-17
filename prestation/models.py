from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from academics.models import AnneeAcademique, Classe, ElementConstitutif, Local, Semestre
from cards.models import Personnel


class BaremePrestation(models.Model):
    CATEGORIE_ENSEIGNEMENT = "enseignement"
    CATEGORIE_ACADEMIQUE = "academique"
    CATEGORIE_JURY = "jury"
    CATEGORIE_LOGISTIQUE = "logistique"

    CATEGORIE_CHOICES = [
        (CATEGORIE_ENSEIGNEMENT, "Enseignement (par période académique)"),
        (CATEGORIE_ACADEMIQUE, "Activités académiques (examens et autres)"),
        (CATEGORIE_JURY, "Jury et soutenance"),
        (CATEGORIE_LOGISTIQUE, "Avantages logistiques"),
    ]

    code = models.CharField(max_length=10, unique=True, verbose_name="Code")
    categorie = models.CharField(max_length=30, choices=CATEGORIE_CHOICES, verbose_name="Catégorie")
    intitule = models.CharField(max_length=255, verbose_name="Intitulé")
    montant = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Montant (CDF)")
    active = models.BooleanField(default=True, verbose_name="Actif")
    ordre = models.PositiveIntegerField(default=1, verbose_name="Ordre")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Barème de prestation"
        verbose_name_plural = "Barèmes de prestation"
        ordering = ["categorie", "ordre", "code"]

    def __str__(self):
        return f"{self.code} - {self.intitule}"


class Prestation(models.Model):
    date_prestation = models.DateField(verbose_name="Date")
    personnel = models.ForeignKey(
        Personnel,
        on_delete=models.PROTECT,
        related_name="prestations",
        verbose_name="Personnel",
    )
    bareme = models.ForeignKey(
        BaremePrestation,
        on_delete=models.PROTECT,
        related_name="prestations",
        verbose_name="Barème",
    )
    categorie = models.CharField(
        max_length=30,
        choices=BaremePrestation.CATEGORIE_CHOICES,
        verbose_name="Catégorie",
    )
    montant = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Montant (CDF)")
    horaire = models.ForeignKey(
        "Horaire",
        on_delete=models.SET_NULL,
        related_name="prestations",
        verbose_name="Horaire",
        null=True,
        blank=True,
    )
    observation = models.TextField(blank=True, null=True, verbose_name="Observation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prestation"
        verbose_name_plural = "Prestations"
        ordering = ["-date_prestation", "-created_at"]

    def __str__(self):
        return f"{self.date_prestation} - {self.personnel}"

    @property
    def section(self):
        if self.horaire and self.horaire.section:
            return self.horaire.section
        return None

    def save(self, *args, **kwargs):
        if self.bareme_id:
            self.categorie = self.bareme.categorie
            self.montant = self.bareme.montant
        super().save(*args, **kwargs)


class Horaire(models.Model):
    direction = models.CharField(
        max_length=255,
        default="DIRECTION DES SYSTEMES D'INFORMATION",
        verbose_name="Direction",
    )
    ecole = models.CharField(
        max_length=255,
        default="ECOLE INFORMATIQUE DES FINANCES",
        verbose_name="École",
    )
    systeme = models.CharField(
        max_length=255,
        default="SYSTÈME LMD/RESEAU",
        verbose_name="Système",
    )
    titre = models.CharField(
        max_length=255,
        default="Horaire des unités d'enseignement",
        verbose_name="Titre",
    )
    annee_academique = models.ForeignKey(
        AnneeAcademique,
        on_delete=models.PROTECT,
        related_name="horaires",
        verbose_name="Année académique",
    )
    semestre = models.ForeignKey(
        Semestre,
        on_delete=models.PROTECT,
        related_name="horaires",
        verbose_name="Semestre",
        null=True,
        blank=True,
    )
    classe = models.ForeignKey(
        Classe,
        on_delete=models.PROTECT,
        related_name="horaires",
        verbose_name="Classe",
    )
    observation = models.TextField(blank=True, null=True, verbose_name="Observation")
    active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Horaire"
        verbose_name_plural = "Horaires"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.classe} - {self.annee_academique.code}"

    @property
    def section(self):
        return self.classe.promotion.filiere.section if self.classe and self.classe.promotion and self.classe.promotion.filiere else None

    @property
    def filiere(self):
        return self.classe.promotion.filiere if self.classe and self.classe.promotion else None

    @property
    def promotion(self):
        return self.classe.promotion if self.classe else None

    @property
    def local(self):
        return self.classe.local if self.classe else None

    @property
    def section_label(self):
        if self.section:
            return self.section.nom or self.section.code or "RESEAU"
        return "RESEAU"

    @property
    def systeme_affichage(self):
        return f"SYSTÈME LMD/{self.section_label}"

    @property
    def titre_document(self):
        classe_label = self.classe.promotion.code if self.classe and self.classe.promotion else self.classe.code
        semestre_label = self.semestre.nom.upper() if self.semestre else "SEMESTRE"
        return f"HORAIRE DES UNITÉS D'ENSEIGNEMENTS DU {semestre_label}: {classe_label}/{self.section_label}"

    @property
    def has_prestation_data(self):
        return self.lignes.exists()


class HoraireLigne(models.Model):
    JOUR_LUNDI = "lundi"
    JOUR_MARDI = "mardi"
    JOUR_MERCREDI = "mercredi"
    JOUR_JEUDI = "jeudi"
    JOUR_VENDREDI = "vendredi"
    JOUR_SAMEDI = "samedi"

    JOUR_CHOICES = [
        (JOUR_LUNDI, "Lundi"),
        (JOUR_MARDI, "Mardi"),
        (JOUR_MERCREDI, "Mercredi"),
        (JOUR_JEUDI, "Jeudi"),
        (JOUR_VENDREDI, "Vendredi"),
        (JOUR_SAMEDI, "Samedi"),
    ]

    JOUR_ORDER = {
        JOUR_LUNDI: 1,
        JOUR_MARDI: 2,
        JOUR_MERCREDI: 3,
        JOUR_JEUDI: 4,
        JOUR_VENDREDI: 5,
        JOUR_SAMEDI: 6,
    }

    horaire = models.ForeignKey(
        Horaire,
        on_delete=models.CASCADE,
        related_name="lignes",
        verbose_name="Horaire",
    )
    jour = models.CharField(max_length=20, choices=JOUR_CHOICES, verbose_name="Jour")
    heure_debut = models.TimeField(verbose_name="Heure début")
    heure_fin = models.TimeField(verbose_name="Heure fin")
    ue_code = models.CharField(max_length=50, blank=True, verbose_name="Code UE")
    element_constitutif = models.ForeignKey(
        ElementConstitutif,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="horaire_lignes",
        verbose_name="Élément constitutif",
    )
    local = models.ForeignKey(
        Local,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="horaire_lignes",
        verbose_name="Local",
    )
    professeur = models.ForeignKey(
        Personnel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="horaire_lignes",
        verbose_name="Professeur",
    )
    ordre = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="Ordre")
    notes = models.CharField(max_length=255, blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ligne d'horaire"
        verbose_name_plural = "Lignes d'horaire"
        ordering = ["horaire", "jour", "heure_debut", "ordre"]

    def __str__(self):
        return f"{self.get_jour_display()} {self.heure_debut}-{self.heure_fin}"

    def clean(self):
        if self.heure_debut and self.heure_fin and self.heure_fin <= self.heure_debut:
            raise ValidationError({"heure_fin": "L'heure de fin doit être supérieure à l'heure de début."})
        if not self.ue_code and not self.element_constitutif:
            raise ValidationError("Veuillez renseigner le code UE ou sélectionner un élément constitutif.")

    @property
    def code_affichage(self):
        if self.element_constitutif:
            return self.element_constitutif.code
        return self.ue_code or "-"

    @property
    def titulaire_affichage(self):
        if not self.professeur:
            return "-"
        return f"{self.professeur.last_name} {self.professeur.first_name}".strip()

    @property
    def local_affichage(self):
        return str(self.local) if self.local else "-"
