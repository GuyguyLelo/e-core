import uuid

from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom de la catégorie")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

class Position(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Poste / Fonction")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Poste / Fonction"
        verbose_name_plural = "Postes / Fonctions"

class Personnel(models.Model):
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, verbose_name="Poste / Fonction")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, verbose_name="Catégorie")
    education_level = models.CharField(max_length=100, verbose_name="Niveau d'études")
    matricule = models.CharField(max_length=50, blank=True, null=True, verbose_name="Matricule")
    photo = models.ImageField(upload_to='personnel/photos/', verbose_name="Photo de profil")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.matricule}"

    class Meta:
        verbose_name = "Personnel"
        verbose_name_plural = "Personnels"

class Card(models.Model):
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, null=True, blank=True, related_name='cards', verbose_name="Personnel")
    issue_date = models.DateField(verbose_name="Date de délivrance")
    expiry_date = models.DateField(verbose_name="Date d'expiration")
    
    generated_card = models.ImageField(upload_to='cards/generated/', blank=True, null=True, verbose_name="Carte générée (Recto)")
    generated_card_back = models.ImageField(upload_to='cards/generated_back/', blank=True, null=True, verbose_name="Carte générée (Verso)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Carte de {self.personnel.first_name} {self.personnel.last_name}"

    def delete(self, *args, **kwargs):
        # Supprime les fichiers images liés lors de la suppression de la carte
        if self.generated_card:
            self.generated_card.delete(save=False)
        if self.generated_card_back:
            self.generated_card_back.delete(save=False)
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = "Carte PVC"
        verbose_name_plural = "Cartes PVC"
        ordering = ['-created_at']


class CardSettings(models.Model):
    """
    Configuration globale pour l'impression des cartes.
    Une seule ligne doit exister (singleton logique).
    """
    training_division_chief_title = models.CharField(
        max_length=150,
        default="Chef des divisions Formation",
        verbose_name="Titre affiché sous la photo"
    )
    training_division_chief_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Nom du Chef des divisions Formation"
    )
    training_division_chief_signature = models.ImageField(
        upload_to="cards/signatures/",
        blank=True,
        null=True,
        verbose_name="Signature (image) Chef divisions Formation"
    )

    digital_seal = models.ImageField(
    upload_to="cards/seals/",
    blank=True,
    null=True,
    verbose_name="Sceau numérique"
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Paramètres cartes (EFI)"
