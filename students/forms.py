"""
Formulaires pour l'application students
"""
from django import forms
from django.contrib.auth.models import User
from .models import Student, Inscription, TypeDocument, DocumentEtudiant, DossierEtudiant
from academics.models import Section, Filiere, Promotion, Classe, AnneeAcademique


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
            'nationalite': forms.TextInput(attrs={'class': 'form-control', 'value': 'Algérienne'}),
            'sexe': forms.Select(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+213 XXX XXX XXX'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adresse complète'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
        }


class StudentImportForm(forms.Form):
    fichier_excel = forms.FileField(
        label="Fichier Excel",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx',
        })
    )


class InscriptionForm(forms.ModelForm):
    section = forms.ModelChoiceField(
        queryset=Section.objects.filter(active=True).order_by('code'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'data-dependent': 'section'}),
        label="Section"
    )
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'data-dependent': 'filiere'}),
        label="Filière"
    )
    promotion_level = forms.ModelChoiceField(
        queryset=Promotion.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'data-dependent': 'promotion'}),
        label="Promotion"
    )

    class Meta:
        model = Inscription
        fields = [
            'etudiant',
            'section', 'filiere', 'promotion_level',
            'classe',
            'annee_academique', 'numero_inscription',
            'statut', 'frais_inscription', 'frais_payes', 'dossier_complet', 'notes'
        ]
        widgets = {
            'etudiant': forms.Select(attrs={'class': 'form-control'}),
            'classe': forms.Select(attrs={'class': 'form-control', 'data-dependent': 'classe'}),
            'annee_academique': forms.Select(attrs={'class': 'form-control'}),
            'numero_inscription': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro d\'inscription'}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'frais_inscription': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'frais_payes': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'dossier_complet': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
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


class DocumentEtudiantForm(forms.ModelForm):
    class Meta:
        model = DocumentEtudiant
        fields = ['etudiant', 'inscription', 'type_document', 'fichier', 'valide', 'notes']
        widgets = {
            'etudiant': forms.Select(attrs={'class': 'form-control'}),
            'inscription': forms.Select(attrs={'class': 'form-control'}),
            'type_document': forms.Select(attrs={'class': 'form-control'}),
            'fichier': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
            'valide': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
