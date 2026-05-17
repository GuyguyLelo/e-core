from django.contrib import admin

from .models import BaremePrestation, Horaire, HoraireLigne


@admin.register(BaremePrestation)
class BaremePrestationAdmin(admin.ModelAdmin):
    list_display = ("code", "categorie", "intitule", "montant", "active", "ordre")
    list_filter = ("categorie", "active")
    search_fields = ("code", "intitule")
    ordering = ("categorie", "ordre", "code")


class HoraireLigneInline(admin.TabularInline):
    model = HoraireLigne
    extra = 0


@admin.register(Horaire)
class HoraireAdmin(admin.ModelAdmin):
    list_display = ("titre", "classe", "annee_academique", "semestre", "active", "created_at")
    list_filter = ("active", "annee_academique", "semestre", "classe")
    search_fields = ("titre", "classe__code", "classe__promotion__code")
    inlines = [HoraireLigneInline]


@admin.register(HoraireLigne)
class HoraireLigneAdmin(admin.ModelAdmin):
    list_display = ("horaire", "jour", "heure_debut", "heure_fin", "code_affichage", "local_affichage", "titulaire_affichage")
    list_filter = ("jour", "horaire__annee_academique", "horaire__semestre")
    search_fields = ("ue_code", "element_constitutif__code", "professeur__first_name", "professeur__last_name")
