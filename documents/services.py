"""
Services de génération de documents PDF avec ReportLab
"""
from io import BytesIO
from django.http import HttpResponse
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from datetime import datetime
from decimal import Decimal

from students.models import Student, Inscription
from academics.models import Semestre, UniteEnseignement, ElementConstitutif
from evaluations.models import Session, Note, NoteEC, NoteUE
from deliberations.models import Deliberation, DecisionJury
from deliberations.services import DeliberationEngine


class PDFGenerator:
    """Classe de base pour la génération de documents PDF"""
    
    def __init__(self, buffer=None):
        self.buffer = buffer if buffer else BytesIO()
        self.width, self.height = A4
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self):
        """Configure les styles personnalisés"""
        # Style titre principal
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Style sous-titre
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Style normal centré
        self.styles.add(ParagraphStyle(
            name='NormalCenter',
            parent=self.styles['Normal'],
            alignment=TA_CENTER,
            fontSize=10
        ))
        
        # Style normal justifié
        self.styles.add(ParagraphStyle(
            name='NormalJustify',
            parent=self.styles['Normal'],
            alignment=TA_JUSTIFY,
            fontSize=10
        ))
        
        # Style pour les en-têtes de tableau
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.white,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER
        ))
        
        # Style pour les cellules de tableau
        self.styles.add(ParagraphStyle(
            name='TableCell',
            parent=self.styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER
        ))


class ReleveNotesGenerator(PDFGenerator):
    """Générateur de relevés de notes"""
    
    def __init__(self, etudiant, session, buffer=None):
        super().__init__(buffer)
        self.etudiant = etudiant
        self.session = session
        self.semestre = session.semestre
        self.promotion = self.semestre.promotion
        self.inscription = Inscription.objects.filter(
            etudiant=etudiant,
            classe__promotion=self.promotion
        ).first()
    
    def generate(self):
        """Génère le relevé de notes"""
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        story = []
        
        # En-tête
        story.extend(self._build_header())
        story.append(Spacer(1, 0.5*cm))
        
        # Informations étudiant
        story.extend(self._build_student_info())
        story.append(Spacer(1, 0.5*cm))
        
        # Informations académiques
        story.extend(self._build_academic_info())
        story.append(Spacer(1, 0.5*cm))
        
        # Tableau des notes
        story.extend(self._build_notes_table())
        story.append(Spacer(1, 0.5*cm))
        
        # Résumé et moyenne
        story.extend(self._build_summary())
        story.append(Spacer(1, 0.5*cm))
        
        # Pied de page
        story.extend(self._build_footer())
        
        doc.build(story)
        return self.buffer
    
    def _build_header(self):
        """Construit l'en-tête du document"""
        elements = []
        
        # Titre
        title = Paragraph("RELEVÉ DE NOTES", self.styles['CustomTitle'])
        elements.append(title)
        elements.append(Spacer(1, 0.3*cm))
        
        # Sous-titre
        subtitle = Paragraph(
            f"Année académique {self.inscription.annee_academique.code}" if self.inscription else "Année académique -",
            self.styles['CustomSubtitle']
        )
        elements.append(subtitle)
        
        return elements
    
    def _build_student_info(self):
        """Construit la section d'informations étudiant"""
        elements = []
        
        data = [
            ['Numéro étudiant:', self.etudiant.numero_etudiant, 'Nom:', self.etudiant.nom],
            ['Prénom:', self.etudiant.prenom, 'Date de naissance:', self.etudiant.date_naissance.strftime('%d/%m/%Y')],
            [
                'Section:',
                (self.inscription.section.nom if self.inscription and self.inscription.section else "-"),
                'Filière:',
                (self.inscription.filiere.nom if self.inscription and self.inscription.filiere else "-"),
            ],
            [
                'Promotion:',
                (self.inscription.promotion.nom if self.inscription else "-"),
                'Classe:',
                (str(self.inscription.classe) if self.inscription and self.inscription.classe else "-"),
            ],
        ]
        
        table = Table(data, colWidths=[3*cm, 5*cm, 3*cm, 5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), TA_LEFT),
            ('ALIGN', (1, 0), (-1, -1), TA_LEFT),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(table)
        return elements
    
    def _build_academic_info(self):
        """Construit la section d'informations académiques"""
        elements = []
        
        data = [
            ['Semestre:', f"{self.semestre.code} - {self.semestre.nom}"],
            ['Session:', f"{self.session.code} - {self.session.nom}"],
            ['Date:', datetime.now().strftime('%d/%m/%Y')],
        ]
        
        table = Table(data, colWidths=[3*cm, 13*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), TA_LEFT),
            ('ALIGN', (1, 0), (1, -1), TA_LEFT),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(table)
        return elements
    
    def _build_notes_table(self):
        """Construit le tableau des notes"""
        elements = []
        
        # En-tête du tableau
        header = ['UE', 'Code UE', 'EC', 'Code EC', 'Note', 'Crédits', 'Statut']
        
        # Récupérer les notes
        engine = DeliberationEngine(self.session)
        resultat = engine.traiter_etudiant(self.etudiant)
        
        data = [header]
        
        # Parcourir les UE
        for ue_id, ue_data in resultat['notes_ue'].items():
            ue = ue_data['ue']
            note_ue = ue_data['note']
            valide_ue = ue_data['valide']
            
            # Parcourir les EC de cette UE
            ecs = ElementConstitutif.objects.filter(ue=ue, active=True).order_by('ordre', 'code')
            first_ec = True
            
            for ec in ecs:
                ec_data = resultat['notes_ec'].get(ec.id, {})
                note_ec = ec_data.get('note', None)
                valide_ec = ec_data.get('valide', False)
                
                if first_ec:
                    # Première ligne avec info UE
                    row = [
                        ue.nom[:30] if len(ue.nom) > 30 else ue.nom,
                        ue.code,
                        ec.nom[:30] if len(ec.nom) > 30 else ec.nom,
                        ec.code,
                        f"{note_ec:.2f}" if note_ec else "Abs",
                        f"{ec.credits_ects}",
                        "✓" if valide_ec else "✗"
                    ]
                    first_ec = False
                else:
                    # Lignes suivantes sans répéter l'UE
                    row = [
                        "",
                        "",
                        ec.nom[:30] if len(ec.nom) > 30 else ec.nom,
                        ec.code,
                        f"{note_ec:.2f}" if note_ec else "Abs",
                        f"{ec.credits_ects}",
                        "✓" if valide_ec else "✗"
                    ]
                
                data.append(row)
            
            # Ligne de synthèse UE
            data.append([
                Paragraph("<b>Moyenne UE</b>", self.styles['TableCell']),
                "",
                "",
                "",
                Paragraph(f"<b>{note_ue:.2f}</b>" if note_ue else "<b>-</b>", self.styles['TableCell']),
                Paragraph(f"<b>{ue.credits_ects}</b>", self.styles['TableCell']),
                Paragraph("<b>✓</b>" if valide_ue else "<b>✗</b>", self.styles['TableCell'])
            ])
            data.append(["", "", "", "", "", "", ""])  # Ligne vide
        
        # Créer le tableau
        table = Table(data, colWidths=[3.5*cm, 1.5*cm, 3.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm])
        table.setStyle(TableStyle([
            # En-tête
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), TA_CENTER),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Corps du tableau
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Lignes de synthèse UE
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E7E6E6')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        
        elements.append(table)
        return elements
    
    def _build_summary(self):
        """Construit la section de résumé"""
        elements = []
        
        engine = DeliberationEngine(self.session)
        resultat = engine.traiter_etudiant(self.etudiant)
        
        moyenne_semestre = resultat['moyenne_semestre']
        credits_obtenus = resultat['credits_obtenus']
        credits_totaux = resultat['credits_totaux']
        
        data = [
            ['Moyenne du semestre:', f"{moyenne_semestre:.2f}/20" if moyenne_semestre else "Non calculable"],
            ['Crédits obtenus:', f"{credits_obtenus:.0f} / {credits_totaux:.0f} ECTS"],
            ['Pourcentage:', f"{(credits_obtenus/credits_totaux*100):.1f}%" if credits_totaux > 0 else "0%"],
        ]
        
        table = Table(data, colWidths=[5*cm, 11*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F2F2F2')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), TA_LEFT),
            ('ALIGN', (1, 0), (1, -1), TA_LEFT),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(table)
        return elements
    
    def _build_footer(self):
        """Construit le pied de page"""
        elements = []
        
        elements.append(Spacer(1, 1*cm))
        
        footer_text = Paragraph(
            f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            self.styles['NormalCenter']
        )
        elements.append(footer_text)
        
        return elements


class ProcesVerbalGenerator(PDFGenerator):
    """Générateur de procès-verbal de délibération"""
    
    def __init__(self, deliberation, buffer=None):
        super().__init__(buffer)
        self.deliberation = deliberation
        self.session = deliberation.session
        self.semestre = self.session.semestre
        self.promotion = self.semestre.promotion
    
    def generate(self):
        """Génère le procès-verbal"""
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        story = []
        
        # En-tête
        story.extend(self._build_header())
        story.append(Spacer(1, 0.5*cm))
        
        # Informations de la délibération
        story.extend(self._build_deliberation_info())
        story.append(Spacer(1, 0.5*cm))
        
        # Composition du jury
        story.extend(self._build_jury_info())
        story.append(Spacer(1, 0.5*cm))
        
        # Tableau des décisions
        story.extend(self._build_decisions_table())
        story.append(Spacer(1, 0.5*cm))
        
        # Statistiques
        story.extend(self._build_statistics())
        story.append(Spacer(1, 0.5*cm))
        
        # Signature
        story.extend(self._build_signature())
        
        doc.build(story)
        return self.buffer
    
    def _build_header(self):
        """Construit l'en-tête"""
        elements = []
        
        title = Paragraph("PROCÈS-VERBAL DE DÉLIBÉRATION", self.styles['CustomTitle'])
        elements.append(title)
        elements.append(Spacer(1, 0.3*cm))
        
        subtitle = Paragraph(
            f"Session {self.session.numero} - {self.semestre.code}",
            self.styles['CustomSubtitle']
        )
        elements.append(subtitle)
        
        return elements
    
    def _build_deliberation_info(self):
        """Construit les informations de délibération"""
        elements = []
        
        data = [
            ['Date de délibération:', self.deliberation.date_deliberation.strftime('%d/%m/%Y')],
            ['Promotion:', self.promotion.code],
            ['Semestre:', f"{self.semestre.code} - {self.semestre.nom}"],
            ['Session:', f"{self.session.code} - {self.session.nom}"],
        ]
        
        table = Table(data, colWidths=[5*cm, 11*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), TA_LEFT),
            ('ALIGN', (1, 0), (1, -1), TA_LEFT),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(table)
        return elements
    
    def _build_jury_info(self):
        """Construit les informations du jury"""
        elements = []
        
        president = self.deliberation.president_jury
        membres = self.deliberation.membres_jury.all()
        
        data = [
            ['Président du jury:', president.get_full_name() if president else "Non défini"],
        ]
        
        if membres.exists():
            membres_list = ", ".join([m.get_full_name() or m.username for m in membres])
            data.append(['Membres du jury:', membres_list])
        
        table = Table(data, colWidths=[5*cm, 11*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), TA_LEFT),
            ('ALIGN', (1, 0), (1, -1), TA_LEFT),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(table)
        return elements
    
    def _build_decisions_table(self):
        """Construit le tableau des décisions"""
        elements = []
        
        decisions = DecisionJury.objects.filter(deliberation=self.deliberation).order_by('rang', 'etudiant__numero_etudiant')
        
        header = ['Rang', 'N° Étudiant', 'Nom', 'Prénom', 'Moyenne', 'Crédits', 'Décision', 'Mention']
        
        data = [header]
        
        for decision in decisions:
            etudiant = decision.etudiant
            row = [
                str(decision.rang) if decision.rang else "-",
                etudiant.numero_etudiant,
                etudiant.nom[:20],
                etudiant.prenom[:20],
                f"{decision.moyenne_semestre:.2f}" if decision.moyenne_semestre else "-",
                f"{decision.credits_obtenus:.0f}/{decision.credits_totaux:.0f}",
                decision.get_decision_display(),
                decision.get_mention_display() if decision.mention else "-"
            ]
            data.append(row)
        
        table = Table(data, colWidths=[1*cm, 2*cm, 3*cm, 3*cm, 1.5*cm, 2*cm, 2.5*cm, 2*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), TA_CENTER),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        return elements
    
    def _build_statistics(self):
        """Construit les statistiques"""
        elements = []
        
        decisions = DecisionJury.objects.filter(deliberation=self.deliberation)
        total = decisions.count()
        
        stats = {
            'admis': decisions.filter(decision='admis').count(),
            'admis_avec_dettes': decisions.filter(decision='admis_avec_dettes').count(),
            'redouble': decisions.filter(decision='redouble').count(),
            'ajourne': decisions.filter(decision='ajourne').count(),
        }
        
        data = [
            ['Total étudiants:', str(total)],
            ['Admis:', str(stats['admis'])],
            ['Admis avec dettes:', str(stats['admis_avec_dettes'])],
            ['Redoublants:', str(stats['redouble'])],
            ['Ajournés:', str(stats['ajourne'])],
        ]
        
        table = Table(data, colWidths=[5*cm, 11*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F2F2F2')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), TA_LEFT),
            ('ALIGN', (1, 0), (1, -1), TA_LEFT),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(table)
        return elements
    
    def _build_signature(self):
        """Construit la section de signature"""
        elements = []
        
        elements.append(Spacer(1, 1*cm))
        
        signature_text = Paragraph(
            "Le Président du Jury<br/><br/>_________________________",
            self.styles['NormalCenter']
        )
        elements.append(signature_text)
        
        if self.deliberation.president_jury:
            president_name = Paragraph(
                self.deliberation.president_jury.get_full_name() or self.deliberation.president_jury.username,
                self.styles['NormalCenter']
            )
            elements.append(Spacer(1, 0.2*cm))
            elements.append(president_name)
        
        return elements


class AttestationGenerator(PDFGenerator):
    """Générateur d'attestations"""
    
    def __init__(self, etudiant, inscription, type_attestation='scolarite', buffer=None):
        super().__init__(buffer)
        self.etudiant = etudiant
        self.inscription = inscription
        self.type_attestation = type_attestation
        self.promotion = inscription.promotion
    
    def generate(self):
        """Génère l'attestation"""
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=3*cm,
            leftMargin=3*cm,
            topMargin=3*cm,
            bottomMargin=3*cm
        )
        
        story = []
        
        # En-tête
        story.extend(self._build_header())
        story.append(Spacer(1, 1*cm))
        
        # Corps de l'attestation
        story.extend(self._build_body())
        story.append(Spacer(1, 1*cm))
        
        # Signature
        story.extend(self._build_signature())
        
        doc.build(story)
        return self.buffer
    
    def _build_header(self):
        """Construit l'en-tête"""
        elements = []
        
        title = Paragraph("ATTESTATION", self.styles['CustomTitle'])
        elements.append(title)
        
        return elements
    
    def _build_body(self):
        """Construit le corps de l'attestation"""
        elements = []
        
        if self.type_attestation == 'scolarite':
            text = f"""
            Je soussigné(e), responsable de la scolarité,
            certifie que <b>{self.etudiant.prenom} {self.etudiant.nom}</b>, né(e) le {self.etudiant.date_naissance.strftime('%d/%m/%Y')}
            à {self.etudiant.lieu_naissance}, de nationalité {self.etudiant.nationalite},
            immatriculé(e) sous le numéro <b>{self.etudiant.numero_etudiant}</b>,
            est régulièrement inscrit(e) en <b>{self.inscription.section.nom if self.inscription.section else '-'}</b> / <b>{self.inscription.filiere.nom if self.inscription.filiere else '-'}</b>
            ({self.inscription.promotion.nom} - Classe {self.inscription.classe.code if self.inscription.classe else '-'})
            pour l'année académique <b>{self.inscription.annee_academique.code}</b>.
            """
        else:
            text = f"""
            Je soussigné(e), responsable de la scolarité,
            certifie que <b>{self.etudiant.prenom} {self.etudiant.nom}</b>, né(e) le {self.etudiant.date_naissance.strftime('%d/%m/%Y')}
            à {self.etudiant.lieu_naissance}, de nationalité {self.etudiant.nationalite},
            immatriculé(e) sous le numéro <b>{self.etudiant.numero_etudiant}</b>,
            est étudiant(e) régulier(ère) de notre établissement.
            """
        
        paragraph = Paragraph(text, self.styles['NormalJustify'])
        elements.append(paragraph)
        
        elements.append(Spacer(1, 0.5*cm))
        
        date_text = Paragraph(
            f"Fait le {datetime.now().strftime('%d/%m/%Y')}",
            self.styles['Normal']
        )
        elements.append(date_text)
        
        return elements
    
    def _build_signature(self):
        """Construit la signature"""
        elements = []
        
        signature_text = Paragraph(
            "Le Directeur/Doyen<br/><br/>_________________________",
            self.styles['NormalCenter']
        )
        elements.append(signature_text)
        
        return elements
