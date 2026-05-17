from django.contrib import admin
from .models import TypeDocumentGenere, DocumentGenere


@admin.register(TypeDocumentGenere)
class TypeDocumentGenereAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'active']
    list_filter = ['active']
    search_fields = ['code', 'nom']


@admin.register(DocumentGenere)
class DocumentGenereAdmin(admin.ModelAdmin):
    list_display = ['type_document', 'etudiant', 'session', 'date_generation', 'genere_par']
    list_filter = ['type_document', 'date_generation', 'session']
    search_fields = ['etudiant__numero_etudiant', 'etudiant__nom', 'etudiant__prenom']
    readonly_fields = ['date_generation', 'created_at', 'updated_at']
