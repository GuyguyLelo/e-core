from django import forms

from academics.models import AnneeAcademique, Classe, ElementConstitutif, Local, Section, Semestre
from cards.models import Personnel

from .models import BaremePrestation, Horaire, HoraireLigne, Prestation


MONTH_CHOICES = [
    ("1", "Janvier"),
    ("2", "Février"),
    ("3", "Mars"),
    ("4", "Avril"),
    ("5", "Mai"),
    ("6", "Juin"),
    ("7", "Juillet"),
    ("8", "Août"),
    ("9", "Septembre"),
    ("10", "Octobre"),
    ("11", "Novembre"),
    ("12", "Décembre"),
]


class BaremePrestationForm(forms.ModelForm):
    class Meta:
        model = BaremePrestation
        fields = ["code", "categorie", "intitule", "montant", "ordre", "active"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: 01"}),
            "categorie": forms.Select(attrs={"class": "form-control"}),
            "intitule": forms.TextInput(attrs={"class": "form-control", "placeholder": "Intitulé du barème"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "1"}),
            "ordre": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class PrestationForm(forms.ModelForm):
    categorie = forms.ChoiceField(
        choices=[("", "---------")] + list(BaremePrestation.CATEGORIE_CHOICES),
        widget=forms.Select(attrs={"class": "form-control", "id": "id_categorie"}),
        label="Catégorie",
    )

    class Meta:
        model = Prestation
        fields = ["date_prestation", "personnel", "categorie", "bareme", "horaire", "observation"]
        widgets = {
            "date_prestation": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "personnel": forms.Select(attrs={"class": "form-control", "id": "id_personnel"}),
            "bareme": forms.Select(attrs={"class": "form-control", "id": "id_bareme"}),
            "horaire": forms.Select(attrs={"class": "form-control"}),
            "observation": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["horaire"].required = False
        self.fields["bareme"].queryset = BaremePrestation.objects.none()
        self.fields["bareme"].required = True
        selected_categorie = self.data.get("categorie") if self.is_bound else None
        if selected_categorie:
            self.fields["bareme"].queryset = BaremePrestation.objects.filter(
                categorie=selected_categorie, active=True
            ).order_by("ordre", "code")
        elif self.instance and self.instance.pk and self.instance.bareme_id:
            self.fields["categorie"].initial = self.instance.categorie
            self.fields["bareme"].queryset = BaremePrestation.objects.filter(
                categorie=self.instance.categorie, active=True
            ).order_by("ordre", "code")

    def clean(self):
        cleaned = super().clean()
        bareme = cleaned.get("bareme")
        categorie = cleaned.get("categorie")
        if bareme and categorie and bareme.categorie != categorie:
            self.add_error("bareme", "Le barème sélectionné ne correspond pas à la catégorie choisie.")
        return cleaned


class CalculPaieForm(forms.Form):
    mois = forms.ChoiceField(
        choices=MONTH_CHOICES,
        label="Mois",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.all().order_by("code"),
        label="Section",
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class FichePrestationJournaliereForm(forms.Form):
    JOUR_CHOICES = [
        ("lundi", "Lundi"),
        ("mardi", "Mardi"),
        ("mercredi", "Mercredi"),
        ("jeudi", "Jeudi"),
        ("vendredi", "Vendredi"),
        ("samedi", "Samedi"),
    ]

    jour = forms.ChoiceField(
        choices=JOUR_CHOICES,
        label="Jour",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    annee_academique = forms.ModelChoiceField(
        queryset=AnneeAcademique.objects.all().order_by("-annee_debut"),
        label="Année académique",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    semestre = forms.ModelChoiceField(
        queryset=Semestre.objects.select_related("promotion").order_by("promotion__code", "numero"),
        label="Semestre",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.all().order_by("code"),
        label="Section",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee_academique"].queryset = AnneeAcademique.objects.all().order_by("-annee_debut")
        self.fields["semestre"].queryset = Semestre.objects.select_related("promotion").order_by("promotion__code", "numero")


class StatistiquesPrestationEnseignementForm(forms.Form):
    date_debut = forms.DateField(
        label="Du",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    date_fin = forms.DateField(
        label="Au",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    annee_academique = forms.ModelChoiceField(
        queryset=AnneeAcademique.objects.all().order_by("-annee_debut"),
        label="Année académique",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    semestre = forms.ModelChoiceField(
        queryset=Semestre.objects.select_related("promotion").order_by("promotion__code", "numero"),
        label="Semestre",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.all().order_by("code"),
        label="Section",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee_academique"].queryset = AnneeAcademique.objects.all().order_by("-annee_debut")
        self.fields["semestre"].queryset = Semestre.objects.select_related("promotion").order_by("promotion__code", "numero")

    def clean(self):
        cleaned = super().clean()
        date_debut = cleaned.get("date_debut")
        date_fin = cleaned.get("date_fin")
        if date_debut and date_fin and date_debut > date_fin:
            raise forms.ValidationError("La date de début doit être antérieure ou égale à la date de fin.")
        return cleaned


class HoraireForm(forms.ModelForm):
    class Meta:
        model = Horaire
        fields = ["titre", "annee_academique", "semestre", "classe", "observation", "active"]
        widgets = {
            "titre": forms.TextInput(attrs={"class": "form-control"}),
            "annee_academique": forms.Select(attrs={"class": "form-control"}),
            "semestre": forms.Select(attrs={"class": "form-control"}),
            "classe": forms.Select(attrs={"class": "form-control"}),
            "observation": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee_academique"].queryset = AnneeAcademique.objects.all().order_by("-annee_debut")
        self.fields["semestre"].queryset = Semestre.objects.select_related("promotion").order_by("promotion__code", "numero")
        self.fields["classe"].queryset = Classe.objects.select_related("promotion", "promotion__filiere", "promotion__filiere__section", "local").filter(active=True).order_by("promotion__code", "code")


class HoraireLigneForm(forms.ModelForm):
    class Meta:
        model = HoraireLigne
        fields = [
            "jour",
            "heure_debut",
            "heure_fin",
            "ue_code",
            "element_constitutif",
            "local",
            "professeur",
            "ordre",
            "notes",
        ]
        widgets = {
            "jour": forms.Select(attrs={"class": "form-control"}),
            "heure_debut": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "ue_code": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: RES301/EC1"}),
            "element_constitutif": forms.Select(attrs={"class": "form-control"}),
            "local": forms.Select(attrs={"class": "form-control"}),
            "professeur": forms.Select(attrs={"class": "form-control"}),
            "ordre": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "notes": forms.TextInput(attrs={"class": "form-control", "placeholder": "Observation optionnelle"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["element_constitutif"].queryset = ElementConstitutif.objects.select_related(
            "ue", "ue__semestre", "ue__semestre__promotion"
        ).order_by("ue__semestre__promotion__code", "ue__ordre", "ordre", "code")
        self.fields["local"].queryset = Local.objects.filter(active=True).order_by("code")
        self.fields["professeur"].queryset = Personnel.objects.select_related("position", "category").order_by("last_name", "first_name")
        self.fields["ue_code"].required = False
        self.fields["element_constitutif"].required = False
        self.fields["local"].required = False
        self.fields["professeur"].required = False
