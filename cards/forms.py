from django import forms
from .models import Card, Personnel, Position, Category

class PersonnelForm(forms.ModelForm):
    class Meta:
        model = Personnel
        fields = ['first_name', 'last_name', 'position', 'category', 'education_level', 'matricule', 'photo']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'education_level': forms.TextInput(attrs={'class': 'form-control'}),
            'matricule': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'photo': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control', 'capture': 'user'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')

        if first_name and last_name:
            qs = Personnel.objects.filter(first_name__iexact=first_name, last_name__iexact=last_name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError("Un personnel avec ce prénom et ce nom est déjà enregistré.")
        return cleaned_data


class PersonnelImportForm(forms.Form):
    fichier_excel = forms.FileField(
        label="Fichier Excel",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx',
        })
    )

class CardForm(forms.ModelForm):
    personnel = forms.ModelChoiceField(
        queryset=Personnel.objects.all(),
        label="Personnel",
        widget=forms.Select(attrs={'class': 'form-select select2'})
    )

    class Meta:
        model = Card
        fields = ['personnel', 'issue_date', 'expiry_date']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        personnel = cleaned_data.get('personnel')
        
        import datetime
        today = datetime.date.today()
        
        if personnel:
            # Vérifier s'il y a une carte active pour ce personnel
            active_cards = Card.objects.filter(personnel=personnel, expiry_date__gte=today)
            if self.instance and self.instance.pk:
                active_cards = active_cards.exclude(pk=self.instance.pk)
            
            if active_cards.exists():
                raise forms.ValidationError("Ce personnel possède déjà une carte en cours de validité (non expirée). Impossible de créer une nouvelle carte.")
                
        return cleaned_data