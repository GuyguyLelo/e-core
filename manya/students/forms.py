"""
Formulaires pour l'application students
"""
from django import forms
from django.contrib.auth.models import User
from .models import Student, Inscription, TypeDocument, DocumentEtudiant, DossierEtudiant
from academics.models import Section, Filiere, Promotion, Classe, AnneeAcademique
from academics.utils import ActiveAnneeModelFormMixin


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'numero_etudiant', 'nom', 'prenom', 'date_naissance',
            'lieu_naissance', 'nationalite', 'sexe', 'telephone',
            'email', 'adresse', 'photo', 'statut'
        ]
        widgets = {
            'numero_etudiant': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: ETU2024001'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de famille'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'}),
            'date_naissance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lieu_naissance': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lieu de naissance'}),
            'nationalite': forms.Select(attrs={'class': 'form-select'}),
            'sexe': forms.Select(attrs={'class': 'form-select'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+213 XXX XXX XXX'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adresse complète'}),
            'photo': forms.FileInput(attrs={'class': 'd-none', 'accept': 'image/*'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sexe_field = self.fields['sexe']
        sexe_field.choices = [('', 'Choisir...')] + list(sexe_field.choices)


class StudentImportForm(forms.Form):
    fichier_excel = forms.FileField(
        label="Fichier Excel",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx',
        })
    )


class StudentListFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Rechercher",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'N°, nom ou prénom…',
        }),
    )
    statut = forms.ChoiceField(
        required=False,
        label="Statut",
        choices=[('', 'Tous les statuts')],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.filter(active=True).order_by('code'),
        required=False,
        label="Filière",
        empty_label="Toutes les filières",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['statut'].choices = [('', 'Tous les statuts')] + list(Student._meta.get_field('statut').choices)


class InscriptionListFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Rechercher",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'N° inscription, étudiant…',
        }),
    )
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.filter(active=True).order_by('code'),
        required=False,
        label="Filière",
        empty_label="Toutes les filières",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    classe = forms.ModelChoiceField(
        queryset=Classe.objects.none(),
        required=False,
        label="Classe",
        empty_label="Toutes les classes",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    statut = forms.ChoiceField(
        required=False,
        label="Statut",
        choices=[('', 'Tous les statuts')],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    annee = forms.ModelChoiceField(
        queryset=AnneeAcademique.objects.all().order_by('-annee_debut'),
        required=False,
        label="Année académique",
        empty_label="Toutes les années",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    dossier = forms.ChoiceField(
        required=False,
        label="Dossier",
        choices=[
            ('', 'Tous'),
            ('1', 'Complet'),
            ('0', 'Incomplet'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['statut'].choices = [('', 'Tous les statuts')] + list(
            Inscription._meta.get_field('statut').choices
        )
        classe_qs = (
            Classe.objects.filter(active=True)
            .select_related('promotion', 'promotion__filiere')
            .order_by('promotion__code', 'code')
        )
        filiere_id = self.data.get('filiere') if self.is_bound else None
        if not filiere_id and not self.is_bound:
            filiere_id = self.initial.get('filiere')
        if filiere_id:
            classe_qs = classe_qs.filter(promotion__filiere_id=filiere_id)
        self.fields['classe'].queryset = classe_qs


class InscriptionForm(ActiveAnneeModelFormMixin, forms.ModelForm):
    section = forms.ModelChoiceField(
        queryset=Section.objects.filter(active=True).order_by('code'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'data-dependent': 'section'}),
        label="Section"
    )
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'data-dependent': 'filiere'}),
        label="Filière"
    )
    promotion_level = forms.ModelChoiceField(
        queryset=Promotion.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'data-dependent': 'promotion'}),
        label="Promotion"
    )

    class Meta:
        model = Inscription
        fields = [
            'etudiant',
            'section', 'filiere', 'promotion_level',
            'classe',
            'numero_inscription',
            'statut', 'notes'
        ]
        widgets = {
            'etudiant': forms.Select(attrs={'class': 'form-select'}),
            'classe': forms.Select(attrs={'class': 'form-select', 'data-dependent': 'classe'}),
            'numero_inscription': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: INS-2025-001',
            }),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observations ou remarques (optionnel)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si on édite une inscription existante, pré-remplir la chaîne hiérarchique
        existing_classe = getattr(self.instance, 'classe', None)
        if existing_classe_id := getattr(existing_classe, 'id', None):
            promo = existing_classe.promotion
            fil = promo.filiere
            sec = fil.section
            if sec:
                self.fields['section'].initial = sec
                self.fields['filiere'].queryset = Filiere.objects.filter(section=sec, active=True).order_by('code')
                self.fields['filiere'].initial = fil
            self.fields['promotion_level'].queryset = Promotion.objects.filter(filiere=fil, active=True).order_by('ordre', 'code')
            self.fields['promotion_level'].initial = promo
            self.fields['classe'].queryset = Classe.objects.filter(promotion=promo, active=True).order_by('code')
        else:
            self.fields['classe'].queryset = Classe.objects.filter(active=True).order_by('code')[:0]

        # Si le POST contient des valeurs, charger les querysets correspondants
        data = self.data or None
        if data:
            section_id = data.get('section')
            if section_id:
                self.fields['filiere'].queryset = Filiere.objects.filter(section_id=section_id, active=True).order_by('code')

            filiere_id = data.get('filiere')
            if filiere_id:
                self.fields['promotion_level'].queryset = Promotion.objects.filter(filiere_id=filiere_id, active=True).order_by('ordre', 'code')

            promotion_id = data.get('promotion_level')
            if promotion_id:
                self.fields['classe'].queryset = Classe.objects.filter(promotion_id=promotion_id, active=True).order_by('code')

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('classe'):
            raise forms.ValidationError("Veuillez sélectionner une classe.")
        return cleaned


class TypeDocumentForm(forms.ModelForm):
    class Meta:
        model = TypeDocument
        fields = ['code', 'nom', 'description', 'obligatoire', 'ordre', 'active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code du type'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du document'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'obligatoire': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DocumentListFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Rechercher",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'N° étudiant, nom, type…',
        }),
    )
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.filter(active=True).order_by('code'),
        required=False,
        label="Filière",
        empty_label="Toutes les filières",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    promotion = forms.ModelChoiceField(
        queryset=Promotion.objects.filter(active=True).select_related('filiere').order_by('filiere__code', 'ordre'),
        required=False,
        label="Promotion",
        empty_label="Toutes les promotions",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    annee = forms.ModelChoiceField(
        queryset=AnneeAcademique.objects.all().order_by('-annee_debut'),
        required=False,
        label="Année académique",
        empty_label="Toutes les années",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        promotion_qs = Promotion.objects.filter(active=True).select_related('filiere').order_by('filiere__code', 'ordre')
        filiere_id = self.data.get('filiere') if self.is_bound else None
        if not filiere_id and not self.is_bound:
            filiere_id = self.initial.get('filiere')
        if filiere_id:
            promotion_qs = promotion_qs.filter(filiere_id=filiere_id)
        self.fields['promotion'].queryset = promotion_qs


class DocumentEtudiantForm(forms.ModelForm):
    class Meta:
        model = DocumentEtudiant
        fields = ['inscription', 'type_document', 'fichier', 'valide', 'notes']
        widgets = {
            'inscription': forms.Select(attrs={'class': 'form-select'}),
            'type_document': forms.Select(attrs={'class': 'form-select'}),
            'fichier': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
            'valide': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, promotion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['inscription'].required = True
        self.fields['inscription'].label = "Inscription (étudiant / promotion)"

        qs = (
            Inscription.objects.select_related(
                'etudiant',
                'classe',
                'classe__promotion',
                'classe__promotion__filiere',
                'annee_academique',
            )
            .exclude(statut='desinscrit')
            .order_by('etudiant__numero_etudiant')
        )
        annee = AnneeAcademique.get_active()
        if annee:
            qs = qs.filter(annee_academique=annee)
        if promotion:
            qs = qs.filter(classe__promotion=promotion)
        self.fields['inscription'].queryset = qs
        self.fields['inscription'].label_from_instance = self._inscription_label

    @staticmethod
    def _inscription_label(inscription):
        promo = inscription.classe.promotion if inscription.classe_id else None
        classe = inscription.classe.code if inscription.classe_id else "—"
        promo_code = promo.code if promo else "—"
        return (
            f"{inscription.etudiant.numero_etudiant} — {inscription.etudiant.nom_complet} "
            f"({promo_code} / {classe})"
        )

    def clean(self):
        cleaned = super().clean()
        inscription = cleaned.get('inscription')
        type_document = cleaned.get('type_document')
        if inscription:
            cleaned['etudiant'] = inscription.etudiant
        if inscription and type_document:
            duplicates = DocumentEtudiant.objects.filter(
                inscription=inscription,
                type_document=type_document,
            )
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise forms.ValidationError(
                    "Ce type de document existe déjà pour cette inscription."
                )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.inscription_id:
            instance.etudiant_id = instance.inscription.etudiant_id
        if commit:
            instance.save()
        return instance
