"""
Moteur de délibération LMD - Service de calcul des notes, compensation, capitalisation
"""
from decimal import Decimal
from django.db.models import Q, Sum, Avg, Count
from django.core.exceptions import ValidationError
from academics.models import Semestre, UniteEnseignement, ElementConstitutif
from students.models import Student, Inscription
from evaluations.models import (
    Session, Evaluation, Note, NoteEC, NoteUE, TypeEvaluation
)
from deliberations.models import ParametresLMD, Deliberation, DecisionJury


class DeliberationEngine:
    """
    Moteur de délibération LMD
    
    Responsabilités :
    1. Calculer les notes EC (moyenne pondérée des évaluations)
    2. Calculer les notes UE (moyenne pondérée des EC)
    3. Calculer les moyennes de semestre
    4. Appliquer les compensations (intra-UE, intra-semestre, annuelle)
    5. Gérer la capitalisation (UE/EC validés)
    6. Calculer les crédits obtenus
    7. Produire les décisions finales
    """

    def __init__(self, session: Session, promotion):
        self.session = session
        self.semestre = session.semestre
        self.promotion = promotion
        
        # Récupérer les paramètres LMD
        try:
            self.parametres = ParametresLMD.objects.get(promotion=self.promotion)
        except ParametresLMD.DoesNotExist:
            # Créer des paramètres par défaut
            self.parametres = ParametresLMD.objects.create(
                promotion=self.promotion,
                seuil_validation=Decimal('10.00'),
                compensation_intra_ue=True,
                compensation_intra_semestre=True,
                compensation_annuelle=True,
                capitalisation_ue=True,
                capitalisation_ec=True,
                passage_avec_dettes=True,
                seuil_credits_minimum=30
            )

    def calculer_note_ec(self, etudiant: Student, ec: ElementConstitutif) -> Decimal:
        """
        Calcule la note finale d'un étudiant à un EC
        Note = moyenne pondérée des évaluations de l'EC
        """
        evaluations = Evaluation.objects.filter(
            ec=ec,
            session=self.session,
            active=True
        )
        
        if not evaluations.exists():
            return None
        
        total_pondere = Decimal('0.00')
        total_coefficients = Decimal('0.00')
        
        for evaluation in evaluations:
            try:
                note_obj = Note.objects.get(etudiant=etudiant, evaluation=evaluation)
                
                if note_obj.absent and not note_obj.justifie:
                    # Absence non justifiée = 0
                    note_finale = Decimal('0.00')
                elif note_obj.absent and note_obj.justifie:
                    # Absence justifiée = ne compte pas dans la moyenne
                    continue
                else:
                    note_finale = note_obj.note_finale or Decimal('0.00')
                
                coefficient = evaluation.coefficient
                total_pondere += note_finale * coefficient
                total_coefficients += coefficient
                
            except Note.DoesNotExist:
                # Pas de note = 0
                coefficient = evaluation.coefficient
                total_pondere += Decimal('0.00') * coefficient
                total_coefficients += coefficient
        
        if total_coefficients == 0:
            return None
        
        note_finale = total_pondere / total_coefficients
        return note_finale.quantize(Decimal('0.01'))

    def calculer_note_ue(self, etudiant: Student, ue: UniteEnseignement) -> Decimal:
        """
        Calcule la note finale d'un étudiant à une UE
        Note = moyenne pondérée des EC de l'UE
        """
        ecs = ElementConstitutif.objects.filter(ue=ue, active=True)
        
        if not ecs.exists():
            return None
        
        total_pondere = Decimal('0.00')
        total_coefficients = Decimal('0.00')
        
        for ec in ecs:
            note_ec = self.calculer_note_ec(etudiant, ec)
            
            if note_ec is None:
                continue
            
            coefficient = ec.coefficient
            total_pondere += note_ec * coefficient
            total_coefficients += coefficient
        
        if total_coefficients == 0:
            return None
        
        note_finale = total_pondere / total_coefficients
        return note_finale.quantize(Decimal('0.01'))

    def valider_ec(self, etudiant: Student, ec: ElementConstitutif, note: Decimal) -> bool:
        """
        Détermine si un EC est validé pour un étudiant
        """
        seuil = ec.seuil_validation or self.parametres.seuil_validation
        
        if note is None:
            return False
        
        # Validation directe
        if note >= seuil:
            return True
        
        # Validation par compensation (si autorisée)
        if ec.compensation_autorisee and self.parametres.compensation_intra_ue:
            # Vérifier si la moyenne de l'UE compense
            ue = ec.ue
            note_ue = self.calculer_note_ue(etudiant, ue)
            
            if note_ue and note_ue >= ue.seuil_validation:
                # La moyenne UE compense, tous les EC sont validés
                return True
        
        return False

    def valider_ue(self, etudiant: Student, ue: UniteEnseignement, note: Decimal) -> bool:
        """
        Détermine si une UE est validée pour un étudiant
        """
        seuil = ue.seuil_validation or self.parametres.seuil_validation
        
        if note is None:
            return False
        
        # Validation directe
        if note >= seuil:
            return True
        
        # Validation par compensation intra-semestre (si autorisée)
        if ue.compensation_autorisee and self.parametres.compensation_intra_semestre:
            moyenne_semestre = self.calculer_moyenne_semestre(etudiant)
            if moyenne_semestre and moyenne_semestre >= self.parametres.seuil_validation:
                return True
        
        return False

    def calculer_moyenne_semestre(self, etudiant: Student) -> Decimal:
        """
        Calcule la moyenne du semestre (moyenne pondérée des UE)
        """
        ues = UniteEnseignement.objects.filter(
            semestre=self.semestre,
            active=True
        )
        
        if not ues.exists():
            return None
        
        total_pondere = Decimal('0.00')
        total_coefficients = Decimal('0.00')
        
        for ue in ues:
            note_ue = self.calculer_note_ue(etudiant, ue)
            
            if note_ue is None:
                continue
            
            coefficient = ue.coefficient
            total_pondere += note_ue * coefficient
            total_coefficients += coefficient
        
        if total_coefficients == 0:
            return None
        
        moyenne = total_pondere / total_coefficients
        return moyenne.quantize(Decimal('0.01'))

    def calculer_credits_obtenus(self, etudiant: Student) -> Decimal:
        """
        Calcule le total des crédits obtenus par un étudiant dans le semestre
        """
        ues = UniteEnseignement.objects.filter(
            semestre=self.semestre,
            active=True
        )
        
        total_credits = Decimal('0.00')
        
        for ue in ues:
            note_ue = self.calculer_note_ue(etudiant, ue)
            
            if note_ue is not None and self.valider_ue(etudiant, ue, note_ue):
                # UE validée, crédits obtenus
                total_credits += ue.credits_ects
            elif self.parametres.capitalisation_ue:
                # Vérifier si certains EC sont capitalisés
                ecs = ElementConstitutif.objects.filter(ue=ue, active=True)
                for ec in ecs:
                    note_ec = self.calculer_note_ec(etudiant, ec)
                    if note_ec is not None and self.valider_ec(etudiant, ec, note_ec):
                        if ec.capitalisable:
                            total_credits += ec.credits_ects
        
        return total_credits.quantize(Decimal('0.01'))

    def traiter_etudiant(self, etudiant: Student) -> dict:
        """
        Traite toutes les notes d'un étudiant pour le semestre
        Retourne un dictionnaire avec toutes les informations calculées
        """
        resultat = {
            'etudiant': etudiant,
            'notes_ec': {},
            'notes_ue': {},
            'moyenne_semestre': None,
            'credits_obtenus': Decimal('0.00'),
            'credits_totaux': Decimal('30.00'),
            'ues_validees': [],
            'ecs_valides': [],
        }
        
        # Calculer les notes EC
        ecs = ElementConstitutif.objects.filter(
            ue__semestre=self.semestre,
            active=True
        )
        
        for ec in ecs:
            note_ec = self.calculer_note_ec(etudiant, ec)
            valide = self.valider_ec(etudiant, ec, note_ec) if note_ec else False
            
            resultat['notes_ec'][ec.id] = {
                'ec': ec,
                'note': note_ec,
                'valide': valide,
                'credits': ec.credits_ects if valide else Decimal('0.00')
            }
            
            if valide:
                resultat['ecs_valides'].append(ec)
                resultat['credits_obtenus'] += ec.credits_ects
        
        # Calculer les notes UE
        ues = UniteEnseignement.objects.filter(
            semestre=self.semestre,
            active=True
        )
        
        for ue in ues:
            note_ue = self.calculer_note_ue(etudiant, ue)
            valide = self.valider_ue(etudiant, ue, note_ue) if note_ue else False
            
            resultat['notes_ue'][ue.id] = {
                'ue': ue,
                'note': note_ue,
                'valide': valide,
                'credits': ue.credits_ects if valide else Decimal('0.00')
            }
            
            if valide:
                resultat['ues_validees'].append(ue)
        
        # Calculer la moyenne du semestre
        resultat['moyenne_semestre'] = self.calculer_moyenne_semestre(etudiant)
        
        # Calculer les crédits totaux du semestre
        resultat['credits_totaux'] = sum(ue.credits_ects for ue in ues)
        
        return resultat

    def sauvegarder_notes_calculees(self, etudiant: Student, resultat: dict):
        """
        Sauvegarde les notes calculées dans la base de données
        """
        # Sauvegarder les notes EC
        for ec_id, data in resultat['notes_ec'].items():
            ec = data['ec']
            note_ec, created = NoteEC.objects.update_or_create(
                etudiant=etudiant,
                ec=ec,
                session=self.session,
                defaults={
                    'note_finale': data['note'],
                    'credits_obtenus': data['credits'],
                    'valide': data['valide'],
                    'capitalise': data['valide'] and ec.capitalisable,
                    'calculee_auto': True,
                }
            )
        
        # Sauvegarder les notes UE
        for ue_id, data in resultat['notes_ue'].items():
            ue = data['ue']
            note_ue, created = NoteUE.objects.update_or_create(
                etudiant=etudiant,
                ue=ue,
                session=self.session,
                defaults={
                    'note_finale': data['note'],
                    'credits_obtenus': data['credits'],
                    'valide': data['valide'],
                    'capitalise': data['valide'] and ue.capitalisable,
                    'calculee_auto': True,
                }
            )

    def produire_decision(self, etudiant: Student, resultat: dict) -> str:
        """
        Produit la décision finale pour un étudiant
        """
        moyenne = resultat['moyenne_semestre']
        credits_obtenus = resultat['credits_obtenus']
        credits_totaux = resultat['credits_totaux']
        seuil = self.parametres.seuil_validation
        
        if moyenne is None:
            return 'ajourne'
        
        # Admis si moyenne >= seuil ET crédits >= seuil minimum
        if moyenne >= seuil and credits_obtenus >= self.parametres.seuil_credits_minimum:
            if credits_obtenus < credits_totaux:
                return 'admis_avec_dettes' if self.parametres.passage_avec_dettes else 'redouble'
            return 'admis'
        
        # Redouble si moyenne < seuil OU crédits insuffisants
        if moyenne < seuil or credits_obtenus < self.parametres.seuil_credits_minimum:
            return 'redouble'
        
        return 'ajourne'

    def traiter_tous_etudiants(self):
        """
        Traite tous les étudiants de la promotion pour cette session
        """
        inscriptions = Inscription.objects.filter(
            classe__promotion=self.promotion,
            statut='inscrit'
        ).select_related('etudiant', 'classe')
        resultats = []
        
        for inscription in inscriptions:
            etudiant = inscription.etudiant
            resultat = self.traiter_etudiant(etudiant)
            self.sauvegarder_notes_calculees(etudiant, resultat)
            resultat['decision'] = self.produire_decision(etudiant, resultat)
            resultats.append(resultat)
        
        return resultats
