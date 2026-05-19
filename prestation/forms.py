from datetime import date

from django import forms

from academics.models import AnneeAcademique, Classe, ElementConstitutif, Local, Section, Semestre
from cards.models import Personnel

from .models import BaremePrestation, EnveloppeBudgetaire, Horaire, HoraireLigne, Prestation


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


def _annee_choices():
    current = date.today().year
    return [(year, str(year)) for year in range(current - 5, current + 3)]


class EnveloppeBudgetaireForm(forms.ModelForm):
    class Meta:
        model = EnveloppeBudgetaire
        fields = ["annee", "mois", "montant"]
        widgets = {
            "annee": forms.NumberInput(attrs={"class": "form-control", "min": 2000, "max": 2100}),
            "mois": forms.Select(attrs={"class": "form-control"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and "annee" not in self.initial:
            self.initial["annee"] = date.today().year
        self.fields["mois"].choices = EnveloppeBudgetaire.MOIS_CHOICES


class BaremePrestationForm(forms.ModelForm):
    class Meta:
        model = BaremePrestation
        fields = ["categorie", "periode", "intitule", "montant", "ordre", "active"]
        widgets = {
            "categorie": forms.Select(attrs={"class": "form-control"}),
            "periode": forms.Select(attrs={"class": "form-control"}),
            "intitule": forms.TextInput(attrs={"class": "form-control", "placeholder": "Intitulé du barème"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "1"}),
            "ordre": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class PrestationForm(forms.ModelForm):
    categorie = forms.ChoiceField(
        choices=[("", "---------")] + list(BaremePrestation.CATEGORIE_CHOICES),
        widget=forms.Select(attrs={"class": "form-control", "id": "id_categorie"}),
        label="Type prestation",
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
            ).order_by("ordre", "intitule")
        elif self.instance and self.instance.pk and self.instance.bareme_id:
            self.fields["categorie"].initial = self.instance.categorie
            self.fields["bareme"].queryset = BaremePrestation.objects.filter(
                categorie=self.instance.categorie, active=True
            ).order_by("ordre", "intitule")

    def clean(self):
        cleaned = super().clean()
        bareme = cleaned.get("bareme")
        categorie = cleaned.get("categorie")
        if bareme and categorie and bareme.categorie != categorie:
            self.add_error("bareme", "Le barème sélectionné ne correspond pas au type de prestation choisi.")
        date_prestation = cleaned.get("date_prestation")
        if date_prestation:
            from .services import is_paie_mois_cloturee, get_month_label

            if is_paie_mois_cloturee(date_prestation.year, date_prestation.month):
                self.add_error(
                    "date_prestation",
                    f"La paie de {get_month_label(date_prestation.month)} {date_prestation.year} est clôturée. "
                    "Aucune prestation ne peut être enregistrée ou modifiée pour ce mois.",
                )
        return cleaned


class CloturePaieForm(forms.Form):
    annee = forms.TypedChoiceField(
        choices=[],
        coerce=int,
        label="Année",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    mois = forms.ChoiceField(
        choices=MONTH_CHOICES,
        label="Mois",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee"].choices = _annee_choices()
        if not self.is_bound:
            self.fields["annee"].initial = date.today().year


class CalculPaieForm(forms.Form):
    annee = forms.TypedChoiceField(
        choices=[],
        coerce=int,
        label="Année",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee"].choices = _annee_choices()
        if not self.is_bound:
            self.fields["annee"].initial = date.today().year


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
            "ue_code": forms.HiddenInput(),
            "element_constitutif": forms.Select(attrs={"class": "form-control js-ec-select"}),
            "local": forms.Select(attrs={"class": "form-control"}),
            "professeur": forms.HiddenInput(),
            "ordre": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "notes": forms.TextInput(attrs={"class": "form-control", "placeholder": "Observation optionnelle"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["element_constitutif"].queryset = ElementConstitutif.objects.select_related(
            "ue", "ue__semestre", "ue__semestre__promotion", "professeur"
        ).order_by("ue__semestre__promotion__code", "ue__ordre", "ordre", "code")
        self.fields["local"].queryset = Local.objects.filter(active=True).order_by("code")
        self.fields["professeur"].queryset = Personnel.objects.all()
        self.fields["ue_code"].required = False
        self.fields["element_constitutif"].required = False
        self.fields["local"].required = False
        self.fields["professeur"].required = False
        if self.instance and self.instance.element_constitutif_id and not self.instance.professeur_id:
            ec = self.instance.element_constitutif
            if ec.professeur_id:
                self.initial["professeur"] = ec.professeur_id

    def clean(self):
        cleaned = super().clean()
        ec = cleaned.get("element_constitutif")
        if ec and ec.professeur_id:
            cleaned["professeur"] = ec.professeur
        elif ec:
            cleaned["professeur"] = None
        return cleaned
