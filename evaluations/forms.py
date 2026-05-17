"""
Formulaires pour l'application evaluations
"""
from django import forms
from django.contrib.auth.models import User
from .models import TypeEvaluation, Session, Evaluation, Note
from academics.models import Semestre
from students.models import Student


class TypeEvaluationForm(forms.ModelForm):
    class Meta:
        model = TypeEvaluation
        fields = ['code', 'nom', 'description', 'coefficient', 'note_max', 'ordre', 'active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: CC, TP, EXAM'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du type'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0.1, 'value': 1.0}),
            'note_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0.1, 'max': 20, 'value': 20.0}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = [
            'semestre', 'numero', 'code', 'nom', 'date_debut',
            'date_fin', 'date_deliberation', 'deliberation_faite',
            'verrouillee', 'active'
        ]
        widgets = {
            'semestre': forms.Select(attrs={'class': 'form-control'}),
            'numero': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 2}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code automatique si vide'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom automatique si vide'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_deliberation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'deliberation_faite': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'verrouillee': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class EvaluationForm(forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = [
            'ec', 'session', 'type_evaluation', 'code', 'nom',
            'date_evaluation', 'coefficient', 'note_max',
            'responsable', 'notes', 'active'
        ]
        widgets = {
            'ec': forms.Select(attrs={'class': 'form-control'}),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'type_evaluation': forms.Select(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code automatique si vide'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom automatique si vide'}),
            'date_evaluation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0.1, 'value': 1.0}),
            'note_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0.1, 'max': 20, 'value': 20.0}),
            'responsable': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = [
            'etudiant', 'evaluation', 'note', 'note_sur', 'absent',
            'justifie', 'justificatif', 'notes'
        ]
        widgets = {
            'etudiant': forms.Select(attrs={'class': 'form-control'}),
            'evaluation': forms.Select(attrs={'class': 'form-control'}),
            'note': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 20}),
            'note_sur': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0.01, 'value': 20.0}),
            'absent': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'justifie': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'justificatif': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
