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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image, Flowable as RLFlowable
from reportlab.pdfbase.pdfmetrics import stringWidth
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
    """Générateur de relevés de notes — nouveau format."""

    def __init__(self, etudiant, semestre, filiere, promotion, annee_academique, buffer=None):
        super().__init__(buffer)
        self.etudiant = etudiant
        self.semestre = semestre
        self.filiere = filiere
        self.promotion = promotion
        self.annee_academique = annee_academique
        self.session = semestre.sessions.filter(active=True).first()
        self.inscription = Inscription.objects.filter(
            etudiant=etudiant,
            classe__promotion=promotion,
            annee_academique=annee_academique,
        ).first()
    
    def generate(self):
        from reportlab.platypus import SimpleDocTemplate
        doc = SimpleDocTemplate(self.buffer, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=1.5*cm, bottomMargin=1.5*cm)
        story = []
        story.extend(self._build_header())
        story.append(Spacer(1, 0.4*cm))
        story.append(self._build_student_info())
        story.append(Spacer(1, 0.4*cm))
        story.append(self._build_notes_table())
        story.append(Spacer(1, 0.4*cm))
        story.extend(self._build_signatures())
        doc.build(story)
        return self.buffer
    
    def _rn_style(self, font_size=9, bold=False, color=None, align=TA_LEFT):
        if color is None: color = colors.black
        return ParagraphStyle(
            f'rn_{font_size}_{bold}_{align}',
            fontName='Helvetica-Bold' if bold else 'Helvetica',
            fontSize=font_size, leading=font_size + 3,
            textColor=color, alignment=align,
            spaceBefore=1, spaceAfter=1,
        )

    def _build_header(self):
        return [
            Paragraph("RÉPUBLIQUE DÉMOCRATIQUE DU CONGO", self._rn_style(10, bold=True, align=TA_CENTER)),
            Paragraph("ECOLE INFORMATIQUE DES FINANCES", self._rn_style(9, bold=True, align=TA_CENTER)),
            Spacer(1, 0.2*cm),
            Paragraph(f"RELEVÉ DE NOTES<br/>{self.semestre.code} — {self.promotion.code} — {self.annee_academique.code}",
                      self._rn_style(12, bold=True, align=TA_CENTER)),
        ]
    
    def _build_student_info(self):
        ins = self.inscription
        data = [
            ['Numéro :', self.etudiant.numero_etudiant, 'Nom :', self.etudiant.nom],
            ['Prénom :', self.etudiant.prenom, 'Naissance :', self.etudiant.date_naissance.strftime('%d/%m/%Y')],
            ['Section :', ins.section.nom if ins and ins.section else '-', 'Filière :', self.filiere.nom],
            ['Promotion :', self.promotion.code, 'Année acad. :', self.annee_academique.code],
            ['Semestre :', f"{self.semestre.code} - {self.semestre.nom}", 'Option :', self.filiere.code],
        ]
        t = Table(data, colWidths=[2.5*cm, 5*cm, 2.5*cm, 5*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        return t
    
    def _build_notes_table(self):
        engine = DeliberationEngine(self.session) if self.session else None
        resultat = engine.traiter_etudiant(self.etudiant) if engine else {}

        ues = UniteEnseignement.objects.filter(semestre=self.semestre, active=True).order_by('ordre', 'code')
        header = ['Code UE', 'Libellé', 'Catégorie', 'CC', 'Crédits', 'Note Pondérée']
        data = [header]

        total_credits = 0
        total_np = 0.0
        cat_sum = {'A': 0.0, 'B': 0.0}
        cat_count = {'A': 0, 'B': 0}
        for ue in ues:
            ecs = ElementConstitutif.objects.filter(ue=ue, active=True).order_by('ordre', 'code')
            cat = ue.categorie or 'A'
            first = True
            for ec in ecs:
                ec_data = resultat.get('notes_ec', {}).get(ec.id, {})
                note = ec_data.get('note', None)
                cr = int(ec.credits_ects)
                total_credits += cr
                np = float(note) * cr if note is not None else 0
                total_np += np
                if note is not None:
                    cat_sum[cat] += float(note)
                    cat_count[cat] += 1
                if first:
                    row = [
                        Paragraph(f"<b>{ue.code}</b>", self._rn_style(8, bold=True)),
                        Paragraph(f"<b>{ue.nom[:35]}</b>", self._rn_style(8, bold=True)),
                        cat, '', '', '',
                    ]
                    data.append(row)
                    first = False
                row = ['', f"{ec.code} {ec.nom[:30]}", cat,
                       f"{note:.2f}" if note is not None else '-', str(cr), f"{np:.2f}"]
                data.append(row)

        s = resultat.get('moyenne_semestre', None)
        co = int(resultat.get('credits_obtenus', 0) or 0)
        ct = int(resultat.get('credits_totaux', 0) or 30)
        dec = engine.produire_decision(self.etudiant, resultat) if engine else ''
        mention = self._compute_mention(s)

        moy_a = cat_sum['A'] / cat_count['A'] if cat_count['A'] else 0
        moy_b = cat_sum['B'] / cat_count['B'] if cat_count['B'] else 0

        recap = [
            ['Total', '', '', '', str(total_credits), f"{total_np:.2f}"],
            ['Moyenne A', '', '', '', '', f"{moy_a:.2f}"],
            ['Moyenne B', '', '', '', '', f"{moy_b:.2f}"],
            ['Moyenne Année', '', '', '', '', f"{s:.2f}" if s else '-'],
            ['Crédit Capitalisé', '', '', '', '', str(co)],
            ['Décision Jury', '', '', '', '', self._decision_label(dec)],
            ['Mention', '', '', '', '', mention],
        ]
        data.extend(recap)

        col_w = [2.5*cm, 4.5*cm, 1.8*cm, 1.8*cm, 1.5*cm, 2.5*cm]
        t = Table(data, colWidths=col_w, repeatRows=1)
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('ALIGN', (2, 0), (5, -1), 'CENTER'),
        ]
        for i in range(1, len(data)):
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f5f5f5')))
        t.setStyle(TableStyle(style_cmds))
        return t

    def _build_signatures(self):
        style = self._rn_style(9, align=TA_CENTER)
        sig = [[
            Paragraph("Secrétaire du Jury<br/>_________________________<br/><br/>", style),
            Paragraph("Membres du Jury<br/>_________________________<br/><br/>", style),
            Paragraph("Président du Jury<br/>_________________________<br/><br/>", style),
        ]]
        st = Table(sig, colWidths=[6*cm, 6*cm, 6*cm])
        st.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
        return [Spacer(1, 0.3*cm),
                Paragraph(f"Fait à Kinshasa, le {datetime.now().strftime('%d/%m/%Y')}",
                          self._rn_style(9, align=TA_CENTER)),
                Spacer(1, 0.4*cm), st]

    def _decision_label(self, decision):
        return {'admis': 'Admis', 'admis_avec_dettes': 'Admis avec dettes',
                'redouble': 'Redouble', 'exclu': 'Exclu',
                'ajourne': 'Ajourné', 'report': 'Report'}.get(decision, decision or '-')

    def _compute_mention(self, moyenne):
        if moyenne is None: return '-'
        if moyenne >= 16: return 'Très Bien'
        if moyenne >= 14: return 'Bien'
        if moyenne >= 12: return 'Assez Bien'
        if moyenne >= 10: return 'Passable'
        return 'Insuffisant'


class ProcesVerbalGenerator(PDFGenerator):
    """Générateur de procès-verbal de délibération"""
    
    def __init__(self, deliberation, buffer=None):
        super().__init__(buffer)
        self.deliberation = deliberation
        self.session = deliberation.session
        self.semestre = self.session.semestre
        self.promotion = self.deliberation.promotion
    
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


class RotatedText(RLFlowable):
    """Flowable avec texte tourné (lecture bas→haut) centré dans la cellule."""

    def __init__(self, text, font_name='Helvetica', font_size=8, bold=False, color=None):
        RLFlowable.__init__(self)
        self.text = text
        self.fn = f"{font_name}-Bold" if bold else font_name
        self.fs = font_size
        self.color = color or colors.black

    def wrap(self, availWidth, availHeight):
        self.tw = stringWidth(self.text, self.fn, self.fs)
        self._width = min(self.fs + 4, availWidth)
        self._height = min(self.tw + 4, availHeight)
        return (self._width, self._height)

    def draw(self):
        self.canv.saveState()
        self.canv.translate(self._width * 0.5, self._height * 0.5)
        self.canv.rotate(90)            # texte vers le HAUT (bas→haut)
        self.canv.setFont(self.fn, self.fs)
        self.canv.setFillColor(self.color)
        # drawString : 1er char en bas, dernier en haut
        # Aligné au début (bas) : start = -_height/2
        self.canv.drawString(-self._height * 0.5, -self.fs * 0.3, self.text)
        self.canv.restoreState()


class GrilleNotesGenerator(PDFGenerator):
    """
    Générateur de grille de notes pour le jury (tableau récapitulatif).
    Format paysage A4 – en-têtes UE et EC tournés verticalement.
    """

    WHITE = colors.white
    BLACK = colors.black
    HEADER_BG = colors.HexColor('#1a237e')
    SUBHEADER_BG = colors.HexColor('#283593')
    CAT_BG = colors.HexColor('#fff3e0')
    MAX_BG = colors.HexColor('#e0f2f1')

    def __init__(self, semestre, filiere, promotion, annee_academique, buffer=None):
        super().__init__(buffer)
        self.semestre = semestre
        self.filiere = filiere
        self.promotion = promotion
        self.annee_academique = annee_academique
        self._init_styles()

    def _init_styles(self):
        """Styles Paragraph pour la grille."""
        base = self.styles['Normal']
        self.st_cell = ParagraphStyle('gr_cell', parent=base, fontSize=6, leading=9,
                                       spaceBefore=1, spaceAfter=1)
        self.st_cell_b = ParagraphStyle('gr_cell_b', parent=base, fontSize=6, leading=9,
                                        fontName='Helvetica-Bold', spaceBefore=1, spaceAfter=1)
        self.st_cell_w = ParagraphStyle('gr_cell_w', parent=self.st_cell_b,
                                        textColor=colors.white)
        self.st_left = ParagraphStyle('gr_left', parent=self.st_cell, alignment=TA_LEFT)
        self.st_left_b = ParagraphStyle('gr_left_b', parent=self.st_cell_b, alignment=TA_LEFT)
        self.st_title = ParagraphStyle('gr_title', parent=base, fontSize=9, leading=12,
                                       fontName='Helvetica-Bold', alignment=TA_CENTER,
                                       spaceBefore=1, spaceAfter=1)
        self.st_sig = ParagraphStyle('gr_sig', parent=base, fontSize=8, leading=11,
                                     fontName='Helvetica-Bold', alignment=TA_CENTER,
                                     spaceBefore=1, spaceAfter=1)


    def generate(self):
        from reportlab.platypus import SimpleDocTemplate

        buffer = self.buffer
        landscape_w, landscape_h = 842, 595  # A4 paysage (points)

        doc = SimpleDocTemplate(
            buffer,
            pagesize=(landscape_w, landscape_h),
            rightMargin=1.2*cm,
            leftMargin=1.2*cm,
            topMargin=1.0*cm,
            bottomMargin=1.0*cm,
        )

        data = self._build_grid_data()
        story = []

        # --- Titre général ---
        title_text = (
            f"RÉPUBLIQUE DÉMOCRATIQUE DU CONGO<br/>"
            f"<b>ECOLE INFORMATIQUE DES FINANCES</b><br/>"
            f"Grille des Notes — {self.semestre.code} — {self.promotion.code} | "
            f"Année acad. {self.annee_academique.code} — {self.filiere.nom}"
        )
        story.append(Paragraph(title_text, self.st_title))
        story.append(Spacer(1, 0.3*cm))

        # --- Tableau ---
        table, _ = self._build_table(data)
        story.append(table)

        # --- Signatures ---
        story.append(Spacer(1, 0.8*cm))
        story.extend(self._build_signature_section())

        doc.build(story)
        return buffer

    def _build_grid_data(self):
        from deliberations.services import DeliberationEngine

        session = self.semestre.sessions.filter(active=True).first()
        ues = UniteEnseignement.objects.filter(semestre=self.semestre, active=True).order_by('ordre', 'code')

        all_ecs = []
        column_specs = []
        ue_column_indices = []
        ec_pair_cols = []  # (col_cat, col_credit) pour chaque EC
        col_idx = 0

        for ue in ues:
            ecs = list(ElementConstitutif.objects.filter(ue=ue, active=True).order_by('ordre', 'code'))
            if not ecs:
                continue

            # Colonne UE
            column_specs.append({'type': 'ue', 'obj': ue, 'ecs': ecs})
            ue_column_indices.append(2 + col_idx)
            col_idx += 1

            # Chaque EC → 2 colonnes : catégorie + crédit
            for ec in ecs:
                start = col_idx
                column_specs.append({'type': 'ec_cat', 'obj': ec, 'ue_code': ue.code})
                column_specs.append({'type': 'ec_credit', 'obj': ec, 'ue_code': ue.code})
                ec_pair_cols.append((2 + start, 2 + start + 1))
                all_ecs.append(ec)
                col_idx += 2

        inscriptions = Inscription.objects.filter(
            classe__promotion=self.promotion,
            annee_academique=self.annee_academique,
            statut='inscrit'
        ).select_related('etudiant', 'classe').order_by('etudiant__numero_etudiant')

        engine = DeliberationEngine(session) if session else None
        rows_data = []
        for idx_etud, inscription in enumerate(inscriptions, start=1):
            etudiant = inscription.etudiant
            row = {
                'numero': idx_etud,
                'etudiant': etudiant,
                'notes_ec': {},
                'moy_semestre': None,
                'credit_semestre': 0,
                'decision': '',
            }
            if engine:
                resultat = engine.traiter_etudiant(etudiant)
                for ec in all_ecs:
                    ec_data = resultat['notes_ec'].get(ec.id, {})
                    row['notes_ec'][ec.id] = ec_data.get('note', None)
                row['moy_semestre'] = resultat.get('moyenne_semestre', None)
                row['credit_semestre'] = int(resultat.get('credits_obtenus', 0)) if resultat.get('credits_obtenus') else 0
                row['decision'] = engine.produire_decision(etudiant, resultat)
            else:
                for ec in all_ecs:
                    note_ec = NoteEC.objects.filter(etudiant=etudiant, ec=ec, session=session).first()
                    row['notes_ec'][ec.id] = note_ec.note_finale if note_ec else None
            rows_data.append(row)

        return {
            'column_specs': column_specs,
            'ue_column_indices': ue_column_indices,
            'ec_pair_cols': ec_pair_cols,
            'all_ecs': all_ecs,
            'rows': rows_data,
            'session': session,
        }

    def _build_table(self, data):
        column_specs = data['column_specs']
        ue_column_indices = data['ue_column_indices']
        ec_pair_cols = data['ec_pair_cols']
        all_ecs = data['all_ecs']
        rows_data = data['rows']

        n_cols = len(column_specs)       # UE + ec_cat + ec_credit
        n_summary = 6
        n_header_rows = 3

        usable = 842 - 2.4*cm
        col_n = 0.6*cm
        col_nom = 2.5*cm
        col_ue = 0.6*cm
        col_sum = 1.2*cm
        col_cat = 0.6*cm          # même largeur que col_credit
        col_credit = 0.6*cm

        widths = [col_n, col_nom]
        for spec in column_specs:
            if spec['type'] == 'ue':
                widths.append(col_ue)
            elif spec['type'] == 'ec_cat':
                widths.append(col_cat)
            else:
                widths.append(col_credit)
        for _ in range(n_summary):
            widths.append(col_sum)

        start_sum = 2 + n_cols

        # ========== LIGNE 0 : en-têtes tournés ==========
        row0 = ['', Paragraph("<b>UE</b>", ParagraphStyle('gr_ue', parent=self.st_cell_w, alignment=TA_CENTER))]
        for spec in column_specs:
            code = spec['obj'].code
            nom = spec['obj'].nom or ''
            if len(nom) > 30:
                nom = nom[:27] + '...'
            txt = f"{code} {nom}"
            if spec['type'] == 'ue':
                row0.append(RotatedText(txt, font_size=7, bold=True, color=self.BLACK))
            elif spec['type'] == 'ec_cat':
                row0.append(RotatedText(txt, font_size=6, bold=False, color=self.WHITE))
            else:
                row0.append('')   # ec_credit – fusionné avec ec_cat
        for txt in ["Note Pondérée", "Moyenne A", "Moyenne B",
                     "Moyenne Semestre", "Crédit Semestre", "Décision Semestre"]:
            row0.append(RotatedText(txt, font_size=6, bold=True, color=self.WHITE))

        # ========== LIGNE 1 : Catégorie & Crédit ==========
        row_cat = ['', Paragraph("<b>Catégorie &amp; Crédit</b>", self.st_cell_w)]
        for spec in column_specs:
            if spec['type'] == 'ue':
                row_cat.append('')
            elif spec['type'] == 'ec_cat':
                # Catégorie = celle de l'UE parente
                cat = spec['obj'].ue.categorie if hasattr(spec['obj'], 'ue') and spec['obj'].ue_id else 'A'
                row_cat.append(cat)
            else:
                row_cat.append(f"{int(spec['obj'].credits_ects)}")
        total_credits_all = sum(int(ec.credits_ects) for ec in all_ecs)
        for idx in range(n_summary):
            if idx == 4:  # Crédit Semestre
                row_cat.append(str(total_credits_all))
            else:
                row_cat.append('-')

        # ========== LIGNE 2 : MAXIMA ==========
        row_max = ['', Paragraph("<b>MAXIMA</b>", self.st_cell_w)]
        for spec in column_specs:
            if spec['type'] == 'ec_credit':
                row_max.append('')    # vide pour la colonne crédit
            else:
                row_max.append("20")
        # MAXIMA pour le résumé
        total_credits_all = sum(int(ec.credits_ects) for ec in all_ecs)
        max_np = 20 * total_credits_all
        for idx, v in enumerate([str(max_np), "20", "20", "20", "30", "-"]):
            if idx == 4:  # Crédit Semestre → vide
                row_max.append('')
            else:
                row_max.append(v)

        # ========== LIGNES ÉTUDIANTS ==========
        header_rows = [row0, row_cat, row_max]
        data_rows = list(header_rows)

        for r in rows_data:
            etu = r['etudiant']
            dr = [str(r['numero']), Paragraph(f"{etu.nom} {etu.prenom}", self.st_left)]
            for spec in column_specs:
                if spec['type'] == 'ue':
                    dr.append('')
                elif spec['type'] == 'ec_cat':
                    note = r['notes_ec'].get(spec['obj'].id)
                    dr.append(f"{note:.2f}" if note is not None else "-")
                else:  # ec_credit
                    note = r['notes_ec'].get(spec['obj'].id)
                    if note is not None and note >= 10:
                        dr.append(str(int(spec['obj'].credits_ects)))
                    else:
                        dr.append("0")
            # Note Pondérée = Σ(note_ec × crédit_ec)
            np_val = 0
            for ec in all_ecs:
                n = r['notes_ec'].get(ec.id)
                if n is not None:
                    np_val += float(n) * int(ec.credits_ects)
            dr.append(f"{np_val:.2f}")
            dr.append(f"{r['moy_semestre']:.2f}" if r['moy_semestre'] is not None else "-")
            dr.append(f"{r['moy_semestre']:.2f}" if r['moy_semestre'] is not None else "-")
            dr.append(f"{r['moy_semestre']:.2f}" if r['moy_semestre'] is not None else "-")
            dr.append(str(r['credit_semestre']))
            dr.append(self._decision_label(r['decision']))
            data_rows.append(dr)

        # ========== STYLES ==========
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), self.HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), self.WHITE),
            ('BACKGROUND', (0, 1), (-1, 1), self.CAT_BG),
            ('BACKGROUND', (0, 2), (-1, 2), self.MAX_BG),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 3), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('VALIGN', (2, 0), (start_sum + n_summary - 1, 0), 'BOTTOM'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]

        # SPAN des paires EC sur la ligne 0 (en-tête) – le titre EC couvre ses 2 colonnes
        for c_cat, c_cr in ec_pair_cols:
            style.append(('SPAN', (c_cat, 0), (c_cr, 0)))

        # Couleur UE
        UE_COL_BG = colors.HexColor('#d1d9f0')
        for c in ue_column_indices:
            style.append(('BACKGROUND', (c, 0), (c, len(data_rows) - 1), UE_COL_BG))

        # En-têtes résumé
        for c in range(start_sum, start_sum + n_summary):
            style.append(('BACKGROUND', (c, 0), (c, 0), colors.HexColor('#37474f')))

        # Span N° sur 3 lignes, Nom NON spané (laisser "Catégorie & Crédit" visible)
        style.append(('SPAN', (0, 0), (0, 2)))
        style.append(('BACKGROUND', (0, 0), (1, 2), self.HEADER_BG))
        style.append(('TEXTCOLOR', (0, 0), (1, 0), self.WHITE))
        style.append(('TEXTCOLOR', (1, 0), (1, 0), self.WHITE))
        # (le blanc est géré directement dans les ParagraphStyles)

        # Alternées
        for i in range(3, len(data_rows), 2):
            style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f5f5f5')))
            for c in ue_column_indices:
                style.append(('BACKGROUND', (c, i), (c, i), UE_COL_BG))

        # Fond résumé
        SUM_COL_BG = colors.HexColor('#e8e8e8')
        for c in range(start_sum, start_sum + n_summary):
            style.append(('BACKGROUND', (c, 0), (c, len(data_rows) - 1), SUM_COL_BG))
        style.append(('BACKGROUND', (start_sum, 0), (start_sum + n_summary - 1, 0), colors.HexColor('#37474f')))

        table = Table(data_rows, colWidths=widths, repeatRows=3)
        table.setStyle(TableStyle(style))
        return table, widths

    def _decision_label(self, decision):
        return {
            'admis': 'Admis',
            'admis_avec_dettes': 'Avec dettes',
            'redouble': 'Redouble',
            'exclu': 'Exclu',
            'ajourne': 'Ajourné',
            'report': 'Report',
        }.get(decision, decision or '-')

    def _build_signature_section(self):
        sig_data = [[
            Paragraph("SECRÉTAIRES DU JURY<br/>_________________________<br/><br/>", self.st_sig),
            Paragraph("MEMBRES DU JURY<br/>_________________________<br/><br/>", self.st_sig),
            Paragraph("PRÉSIDENT DU JURY<br/>_________________________<br/><br/>", self.st_sig),
        ]]
        sig_table = Table(sig_data, colWidths=[8*cm, 8*cm, 8*cm])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return [sig_table]
