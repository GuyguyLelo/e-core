"""
Formulaires pour l'application deliberations
"""
from django import forms
from django.contrib.auth.models import User
from .models import ParametresLMD, Deliberation, DecisionJury
from academics.models import Promotion
from evaluations.models import Session
from students.models import Student, Inscription


class ParametresLMDForm(forms.ModelForm):
    class Meta:
        model = ParametresLMD
        fields = [
            'promotion', 'seuil_validation', 'compensation_intra_ue',
            'compensation_intra_semestre', 'compensation_annuelle',
            'capitalisation_ue', 'capitalisation_ec', 'passage_avec_dettes',
            'seuil_credits_minimum'
        ]
        widgets = {
            'promotion': forms.Select(attrs={'class': 'form-control'}),
            'seuil_validation': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0, 'max': 20, 'value': 10.0}),
            'compensation_intra_ue': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compensation_intra_semestre': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compensation_annuelle': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'capitalisation_ue': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'capitalisation_ec': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'passage_avec_dettes': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'seuil_credits_minimum': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'value': 30}),
        }


class DeliberationForm(forms.ModelForm):
    class Meta:
        model = Deliberation
        fields = ['session', 'date_deliberation', 'president_jury', 'membres_jury', 'statut', 'notes']
        widgets = {
            'session': forms.Select(attrs={'class': 'form-control'}),
            'date_deliberation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'president_jury': forms.Select(attrs={'class': 'form-control'}),
            'membres_jury': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 5}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class DecisionJuryForm(forms.ModelForm):
    class Meta:
        model = DecisionJury
        fields = [
            'deliberation', 'etudiant', 'inscription', 'decision',
            'moyenne_semestre', 'credits_obtenus', 'credits_totaux',
            'rang', 'mention', 'notes_jury'
        ]
        widgets = {
            'deliberation': forms.Select(attrs={'class': 'form-control'}),
            'etudiant': forms.Select(attrs={'class': 'form-control'}),
            'inscription': forms.Select(attrs={'class': 'form-control'}),
            'decision': forms.Select(attrs={'class': 'form-control'}),
            'moyenne_semestre': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 20}),
            'credits_obtenus': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0}),
            'credits_totaux': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0, 'value': 30.0}),
            'rang': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'mention': forms.Select(attrs={'class': 'form-control'}),
            'notes_jury': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
