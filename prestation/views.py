from collections import OrderedDict, defaultdict
from datetime import date
from io import BytesIO
import os
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Sum
from django.forms import inlineformset_factory
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    PageBreak,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from academics.models import AnneeAcademique
from cards.models import CardSettings, Personnel
from .forms import BaremePrestationForm, CalculPaieForm, FichePrestationJournaliereForm, HoraireForm, HoraireLigneForm, PrestationForm, StatistiquesPrestationEnseignementForm
from .models import BaremePrestation, Horaire, HoraireLigne, Prestation


HoraireLigneFormSet = inlineformset_factory(
    Horaire,
    HoraireLigne,
    form=HoraireLigneForm,
    extra=18,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


DAY_ORDER = [
    HoraireLigne.JOUR_LUNDI,
    HoraireLigne.JOUR_MARDI,
    HoraireLigne.JOUR_MERCREDI,
    HoraireLigne.JOUR_JEUDI,
    HoraireLigne.JOUR_VENDREDI,
    HoraireLigne.JOUR_SAMEDI,
]

MONTH_LABELS = {
    "1": "Janvier",
    "2": "Février",
    "3": "Mars",
    "4": "Avril",
    "5": "Mai",
    "6": "Juin",
    "7": "Juillet",
    "8": "Août",
    "9": "Septembre",
    "10": "Octobre",
    "11": "Novembre",
    "12": "Décembre",
}


def _get_calcul_annee():
    annee = AnneeAcademique.objects.filter(active=True).order_by("-annee_debut").first()
    if annee:
        return annee
    return AnneeAcademique.objects.order_by("-annee_debut").first()


def _get_prestation_section(prestation):
    horaire = getattr(prestation, "horaire", None)
    if not horaire or not getattr(horaire, "classe", None):
        return None
    promotion = getattr(horaire.classe, "promotion", None)
    filiere = getattr(promotion, "filiere", None) if promotion else None
    return getattr(filiere, "section", None) if filiere else None


def _section_matches_prestation(prestation, section):
    prestation_section = _get_prestation_section(prestation)
    if prestation_section and prestation_section.pk == section.pk:
        return True
    return False


def _collect_fiche_prestations(section, jour_key, semestre, annee_academique):
    day_labels = {
        HoraireLigne.JOUR_LUNDI: "Lundi",
        HoraireLigne.JOUR_MARDI: "Mardi",
        HoraireLigne.JOUR_MERCREDI: "Mercredi",
        HoraireLigne.JOUR_JEUDI: "Jeudi",
        HoraireLigne.JOUR_VENDREDI: "Vendredi",
        HoraireLigne.JOUR_SAMEDI: "Samedi",
    }
    day_key = jour_key
    if not day_key:
        return {
            "lines": [],
            "day_key": None,
            "day_label": "-",
        }

    lines = HoraireLigne.objects.select_related(
        "horaire",
        "horaire__classe",
        "horaire__classe__promotion",
        "horaire__classe__promotion__filiere",
        "horaire__classe__promotion__filiere__section",
        "element_constitutif",
        "local",
        "professeur",
        "professeur__category",
    ).filter(
        horaire__active=True,
        horaire__classe__promotion__filiere__section=section,
        horaire__semestre=semestre,
        horaire__annee_academique=annee_academique,
        jour=day_key,
    ).order_by(
        "horaire__classe__promotion__code",
        "horaire__classe__code",
        "heure_debut",
        "ordre",
    )

    rows = []
    for index, line in enumerate(lines, start=1):
        personnel = line.professeur
        rows.append({
            "numero": index,
            "nom_prenom": f"{personnel.last_name} {personnel.first_name}".strip() if personnel else "-",
            "categorie": personnel.category.name if personnel and personnel.category else "-",
            "ue": f"{line.code_affichage}" if line.code_affichage else "-",
            "heure_debut": line.heure_debut.strftime("%Hh%M"),
            "heure_fin": line.heure_fin.strftime("%Hh%M"),
            "classe": line.horaire.classe.nom if line.horaire and line.horaire.classe else "-",
            "local": line.local.nom if line.local else "-",
            "signature": "",
            "line": line,
        })

    return {
        "lines": rows,
        "day_key": day_key,
        "day_label": day_labels.get(day_key, "-"),
    }


def _format_statistiques_enseignement_range(date_debut, date_fin):
    if date_debut and date_fin:
        return f"du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}"
    if date_debut:
        return f"à partir du {date_debut.strftime('%d/%m/%Y')}"
    if date_fin:
        return f"jusqu'au {date_fin.strftime('%d/%m/%Y')}"
    return "sur la période sélectionnée"


def _get_statistiques_enseignement_ue_code(prestation):
    horaire = prestation.horaire
    if not horaire:
        return prestation.bareme.intitule if prestation.bareme else "-"

    lignes = getattr(horaire, "lignes", None)
    if lignes is not None:
        qs = horaire.lignes.all()
        if prestation.personnel_id:
            qs = qs.filter(professeur_id=prestation.personnel_id)
        ligne = qs.order_by("ordre", "heure_debut").first()
        if ligne:
            code = (ligne.code_affichage or "").strip()
            if code and code != "-":
                return code

    ligne = horaire.lignes.order_by("ordre", "heure_debut").first()
    if ligne:
        code = (ligne.code_affichage or "").strip()
        if code and code != "-":
            return code

    return prestation.bareme.intitule if prestation.bareme else "-"


def _collect_statistiques_prestations_enseignement(section, annee_academique, semestre, date_debut, date_fin):
    prestations = Prestation.objects.select_related(
        "personnel",
        "bareme",
        "horaire",
        "horaire__classe",
        "horaire__classe__promotion",
        "horaire__classe__promotion__filiere",
        "horaire__classe__promotion__filiere__section",
    ).prefetch_related(
        "horaire__lignes",
        "horaire__lignes__element_constitutif",
    ).filter(
        bareme__categorie=BaremePrestation.CATEGORIE_ENSEIGNEMENT,
        date_prestation__range=(date_debut, date_fin),
        horaire__annee_academique=annee_academique,
        horaire__semestre=semestre,
        horaire__classe__promotion__filiere__section=section,
    ).order_by(
        "personnel__last_name",
        "personnel__first_name",
        "date_prestation",
    )

    grouped = OrderedDict()
    for prestation in prestations:
        personnel = prestation.personnel
        if not personnel:
            continue
        ue_label = _get_statistiques_enseignement_ue_code(prestation)
        ue_key = re.sub(r"\s+", " ", ue_label).strip().lower()
        if not ue_key:
            ue_key = f"horaire:{prestation.horaire_id or 'none'}"
        key = (personnel.pk, ue_key)
        if key not in grouped:
            grouped[key] = {
                "personnel": personnel,
                "ue": ue_label or "-",
                "ue_key": ue_key,
                "nombre_prestations": 0,
            }
        grouped[key]["nombre_prestations"] += 1

    rows = []
    for index, item in enumerate(sorted(
        grouped.values(),
        key=lambda row: (
            (row["personnel"].last_name or "").lower(),
            (row["personnel"].first_name or "").lower(),
            (row["ue"] or "").lower(),
        ),
    ), start=1):
        personnel = item["personnel"]
        rows.append({
            "numero": index,
            "nom": personnel.last_name or "",
            "prenom": personnel.first_name or "",
            "nom_prenom": f"{personnel.last_name} {personnel.first_name}".strip(),
            "ue": item["ue"],
            "nombre_prestations": item["nombre_prestations"],
        })

    return {
        "rows": rows,
        "total_lignes": len(prestations),
        "total_lignes_stats": sum(item["nombre_prestations"] for item in rows),
    }


def _collect_paie_data(mois, section):
    prestations_mois = Prestation.objects.select_related(
        "personnel",
        "bareme",
        "horaire",
        "horaire__classe",
        "horaire__classe__promotion",
        "horaire__classe__promotion__filiere",
        "horaire__classe__promotion__filiere__section",
    ).filter(
        date_prestation__month=mois,
    ).order_by("personnel__last_name", "personnel__first_name", "date_prestation")

    prestations_filtrees = [prestation for prestation in prestations_mois if _section_matches_prestation(prestation, section)]
    fallback_used = False
    if not prestations_filtrees and prestations_mois.exists():
        prestations_filtrees = list(prestations_mois)
        fallback_used = True

    grouped = defaultdict(list)
    for prestation in prestations_filtrees:
        grouped[prestation.personnel].append(prestation)

    resultats = []
    for personnel, lignes in grouped.items():
        total_personnel = sum(int(p.montant or 0) for p in lignes)
        resultats.append({
            "personnel": personnel,
            "prestations": lignes,
            "total": total_personnel,
        })

    total_general = sum(item["total"] for item in resultats)
    total_prestations = len(prestations_filtrees)
    total_personnels = len(resultats)
    ids = [p.id for p in prestations_filtrees]
    totals_by_bareme = (
        Prestation.objects.filter(id__in=ids)
        .values("bareme__categorie", "bareme__code", "bareme__intitule")
        .annotate(total=Sum("montant"), nombre=Count("id"))
    ) if ids else []

    return {
        "prestations_mois": prestations_mois,
        "prestations": prestations_filtrees,
        "resultats": resultats,
        "total_general": total_general,
        "total_prestations": total_prestations,
        "total_personnels": total_personnels,
        "totals_by_bareme": totals_by_bareme,
        "fallback_used": fallback_used,
    }


def _collect_individual_bulletin(personnel, mois, section):
    prestations = Prestation.objects.select_related(
        "personnel",
        "bareme",
        "horaire",
        "horaire__classe",
        "horaire__classe__promotion",
        "horaire__classe__promotion__filiere",
        "horaire__classe__promotion__filiere__section",
    ).filter(
        personnel=personnel,
        date_prestation__month=mois,
    ).order_by("date_prestation")
    prestations = [prestation for prestation in prestations if _section_matches_prestation(prestation, section)]
    total_general = sum(int(prestation.montant or 0) for prestation in prestations)
    return {
        "personnel": personnel,
        "prestations": prestations,
        "total_general": total_general,
    }


def _build_header_table(body_style, direction, ecole, systeme_affichage, right_title, right_value):
    logo = _logo_flowable(_asset_path("static", "images", "logoeifi.png"), width_mm=20)
    header_table = Table([[
        logo if logo else Paragraph("EIFI", ParagraphStyle("LogoFallback", parent=body_style, fontName="Helvetica-Bold", fontSize=16, textColor=colors.white)),
        Paragraph(f"<b>{direction}</b><br/>{ecole}<br/>{systeme_affichage}", ParagraphStyle(
            "HeaderTitle",
            parent=body_style,
            fontName="Helvetica-Bold",
            fontSize=11.2,
            leading=13,
            textColor=colors.white,
        )),
        Paragraph(f"<b>{right_title}</b><br/>{right_value}", ParagraphStyle(
            "HeaderRight",
            parent=body_style,
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.white,
        )),
    ]], colWidths=[24 * mm, 112 * mm, 40 * mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#0f172a")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#334155")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return header_table


def _build_signature_footer(body_style):
    settings_row = CardSettings.objects.first()
    chief_name = settings_row.training_division_chief_name if settings_row else ""
    right_footer_style = ParagraphStyle(
        "RightFooter",
        parent=body_style,
        alignment=TA_LEFT,
        leading=9,
        spaceBefore=0,
        spaceAfter=0,
    )
    footer_block = [
        Paragraph(f"Fait à Kinshasa le {date.today().strftime('%d/%m/%Y')}", right_footer_style),
        Spacer(1, 0.8 * mm),
        Paragraph("<u><b>LE CHEF DE DIVISION FORMATION</b></u>", right_footer_style),
    ]
    if chief_name:
        footer_block.append(Spacer(1, 0.8 * mm))
        footer_block.append(Paragraph(chief_name, right_footer_style))
    footer_table = Table([["", footer_block]], colWidths=[108 * mm, 72 * mm])
    footer_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return footer_table


def _group_lines_by_day(lines):
    grouped = OrderedDict((day, []) for day in DAY_ORDER)
    for line in lines:
        grouped.setdefault(line.jour, []).append(line)
    return grouped


def _format_time_range(line):
    return f"{line.heure_debut.strftime('%Hh%M')}-{line.heure_fin.strftime('%Hh%M')}"


def _unique_legend_items(lines):
    seen = set()
    items = []
    for line in lines:
        code = line.code_affichage
        key = (code, line.titulaire_affichage)
        if key in seen:
            continue
        seen.add(key)
        title = line.element_constitutif.nom if line.element_constitutif else code
        items.append((title, line.titulaire_affichage, code))
    return items


def _asset_path(*parts):
    return os.path.join(str(settings.BASE_DIR), *parts)


def _logo_flowable(path, width_mm=18):
    if not path or not os.path.exists(path):
        return None
    img = RLImage(path)
    img.drawHeight = width_mm * mm * img.drawHeight / img.drawWidth
    img.drawWidth = width_mm * mm
    return img


def _draw_page_number(c, doc):
    page_number = c.getPageNumber()
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawRightString(doc.pagesize[0] - 15 * mm, 10 * mm, f"Page {page_number}")
    c.restoreState()


@login_required
def bareme_list(request):
    baremes = BaremePrestation.objects.all().order_by("categorie", "ordre", "code")
    return render(request, "prestation/bareme_list.html", {"baremes": baremes})


@login_required
def bareme_create(request):
    if request.method == "POST":
        form = BaremePrestationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Barème enregistré avec succès.")
            return redirect("prestation:bareme_list")
    else:
        form = BaremePrestationForm()
    return render(request, "prestation/bareme_form.html", {"form": form, "title": "Nouveau barème"})


@login_required
def bareme_update(request, pk):
    bareme = get_object_or_404(BaremePrestation, pk=pk)
    if request.method == "POST":
        form = BaremePrestationForm(request.POST, instance=bareme)
        if form.is_valid():
            form.save()
            messages.success(request, "Barème modifié avec succès.")
            return redirect("prestation:bareme_list")
    else:
        form = BaremePrestationForm(instance=bareme)
    return render(request, "prestation/bareme_form.html", {"form": form, "title": "Modifier le barème", "bareme": bareme})


@login_required
def bareme_delete(request, pk):
    bareme = get_object_or_404(BaremePrestation, pk=pk)
    if request.method == "POST":
        bareme.delete()
        messages.success(request, "Barème supprimé avec succès.")
        return redirect("prestation:bareme_list")
    return render(request, "prestation/bareme_confirm_delete.html", {"bareme": bareme})


@login_required
def prestation_list(request):
    prestations = Prestation.objects.select_related(
        "personnel",
        "bareme",
        "horaire",
    ).all()
    return render(request, "prestation/prestation_list.html", {"prestations": prestations})


@login_required
def prestation_create(request):
    if request.method == "POST":
        form = PrestationForm(request.POST)
        if form.is_valid():
            prestation = form.save(commit=False)
            prestation.save()
            messages.success(request, "Prestation enregistrée avec succès.")
            return redirect("prestation:prestation_list")
    else:
        form = PrestationForm()
    return render(request, "prestation/prestation_form.html", {"form": form, "title": "Nouvelle prestation"})


@login_required
def prestation_update(request, pk):
    prestation = get_object_or_404(Prestation, pk=pk)
    if request.method == "POST":
        form = PrestationForm(request.POST, instance=prestation)
        if form.is_valid():
            prestation = form.save(commit=False)
            prestation.save()
            messages.success(request, "Prestation modifiée avec succès.")
            return redirect("prestation:prestation_list")
    else:
        form = PrestationForm(instance=prestation)
    return render(request, "prestation/prestation_form.html", {"form": form, "title": "Modifier la prestation", "prestation": prestation})


@login_required
def prestation_delete(request, pk):
    prestation = get_object_or_404(Prestation, pk=pk)
    if request.method == "POST":
        prestation.delete()
        messages.success(request, "Prestation supprimée avec succès.")
        return redirect("prestation:prestation_list")
    return render(request, "prestation/prestation_confirm_delete.html", {"prestation": prestation})


@login_required
def api_baremes_by_categorie(request):
    categorie = request.GET.get("categorie")
    baremes = BaremePrestation.objects.filter(active=True)
    if categorie:
        baremes = baremes.filter(categorie=categorie)
    data = [
        {
            "id": bareme.id,
            "code": bareme.code,
            "label": f"{bareme.code} - {bareme.intitule}",
            "montant": str(bareme.montant),
            "categorie": bareme.categorie,
        }
        for bareme in baremes.order_by("ordre", "code")
    ]
    return JsonResponse({"results": data})


@login_required
def calcul_paie(request):
    calculation = None
    resultats = []
    total_general = 0
    total_prestations = 0
    total_personnels = 0
    annee_academique = _get_calcul_annee()

    if request.method == "POST":
        form = CalculPaieForm(request.POST)
        if form.is_valid():
            mois = int(form.cleaned_data["mois"])
            section = form.cleaned_data["section"]
            paie_data = _collect_paie_data(mois, section)
            resultats = paie_data["resultats"]
            total_general = paie_data["total_general"]
            total_prestations = paie_data["total_prestations"]
            total_personnels = paie_data["total_personnels"]
            if paie_data["fallback_used"]:
                messages.warning(
                    request,
                    "Aucune prestation n'est rattachée à cette section dans les données. Le calcul affiche donc toutes les prestations du mois sélectionné.",
                )
            elif not paie_data["prestations"]:
                messages.info(request, "Aucune prestation trouvée pour ce mois et cette section.")
            calculation = {
                "mois": MONTH_LABELS.get(str(mois), str(mois)),
                "annee_academique": annee_academique,
                "section": section,
                "prestations": paie_data["prestations"],
                "prestations_trouvees": paie_data["total_prestations"],
                "totals_by_bareme": paie_data["totals_by_bareme"],
            }
    else:
        form = CalculPaieForm()

    return render(request, "prestation/calcul_paie.html", {
        "form": form,
        "calculation": calculation,
        "annee_academique": annee_academique,
        "resultats": resultats,
        "total_general": total_general,
        "total_prestations": total_prestations,
        "total_personnels": total_personnels,
    })


@login_required
def bulletin_paie(request):
    annee_academique = _get_calcul_annee()
    form = CalculPaieForm(request.GET or None)
    bulletin = None
    download_query = ""

    if form.is_valid():
        mois = int(form.cleaned_data["mois"])
        section = form.cleaned_data["section"]
        paie_data = _collect_paie_data(mois, section)
        if paie_data["fallback_used"]:
            messages.warning(
                request,
                "Aucune prestation n'est rattachée à cette section dans les données. Le bulletin affiche donc toutes les prestations du mois sélectionné.",
            )
        elif not paie_data["prestations"]:
            messages.info(request, "Aucune prestation trouvée pour ce mois et cette section.")

        section_label = section.nom or section.code or "SECTION"
        bulletin = {
            "mois": MONTH_LABELS.get(str(mois), str(mois)),
            "mois_numero": mois,
            "section": section,
            "section_label": section_label,
            "annee_academique": annee_academique,
            "resultats": paie_data["resultats"],
            "total_general": paie_data["total_general"],
            "total_prestations": paie_data["total_prestations"],
            "total_personnels": paie_data["total_personnels"],
        }
        download_query = f"mois={mois}&section={section.pk}"

    return render(request, "prestation/bulletin_paie.html", {
        "form": form,
        "bulletin": bulletin,
        "annee_academique": annee_academique,
        "download_query": download_query,
    })


def _build_bulletin_pdf(bulletin):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BulletinTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14.2,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#475569"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodySmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
    )
    center_style = ParagraphStyle(
        "CenterSmall",
        parent=body_style,
        alignment=TA_CENTER,
    )

    story = []
    bulletin_title = bulletin.get("titre") or (
        f"BULLETIN DE PAIE - {bulletin['mois']} {bulletin['annee_academique'].code if bulletin.get('annee_academique') else ''}"
    )
    direction = "DIRECTION DES SYSTEMES D'INFORMATION"
    ecole = "ECOLE INFORMATIQUE DES FINANCES"
    systeme_affichage = f"SYSTÈME LMD/{bulletin['section_label']}"
    year_text = bulletin["annee_academique"].code if bulletin.get("annee_academique") else "AUTOMATIQUE"
    story.append(_build_header_table(body_style, direction, ecole, systeme_affichage, "ANNEE ACADEMIQUE", year_text))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"<u><b>{bulletin_title}</b></u>",
        title_style,
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Section : <b>{bulletin['section_label']}</b>",
        ParagraphStyle(
            "BulletinMeta",
            parent=body_style,
            fontSize=8.6,
            leading=10.2,
            textColor=colors.HexColor("#334155"),
        ),
    ))
    story.append(Spacer(1, 3 * mm))

    for index, item in enumerate(bulletin["resultats"]):
        if index > 0:
            story.append(PageBreak())
            story.append(_build_header_table(body_style, direction, ecole, systeme_affichage, "ANNEE ACADEMIQUE", year_text))
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph(
                f"<u><b>{bulletin_title}</b></u>",
                title_style,
            ))
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(
                f"Section : <b>{bulletin['section_label']}</b>",
                ParagraphStyle(
                    "BulletinMetaRepeat",
                    parent=body_style,
                    fontSize=8.6,
                    leading=10.2,
                    textColor=colors.HexColor("#334155"),
                ),
            ))
            story.append(Spacer(1, 3 * mm))

        info_table = Table([[
            Paragraph("<b>Personnel</b>", body_style),
            Paragraph(item["personnel"].__str__(), body_style),
            Paragraph("<b>Nombre de prestations</b>", body_style),
            Paragraph(str(len(item["prestations"])), body_style),
        ], [
            Paragraph("<b>Total à payer</b>", body_style),
            Paragraph(f"{int(item['total']):,} CDF".replace(",", " "), body_style),
            Paragraph("<b>Mois</b>", body_style),
            Paragraph(bulletin["mois"], body_style),
        ]], colWidths=[35 * mm, 65 * mm, 40 * mm, 42 * mm])
        info_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef2ff")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 4 * mm))

        table_data = [[
            Paragraph("<b>Date</b>", center_style),
            Paragraph("<b>Barème</b>", center_style),
            Paragraph("<b>Catégorie</b>", center_style),
            Paragraph("<b>Montant</b>", center_style),
        ]]
        for prestation in item["prestations"]:
            table_data.append([
                Paragraph(prestation.date_prestation.strftime("%d/%m/%Y"), body_style),
                Paragraph(str(prestation.bareme), body_style),
                Paragraph(prestation.get_categorie_display(), body_style),
                Paragraph(f"{int(prestation.montant):,} CDF".replace(",", " "), body_style),
            ])
        table_data.append([
            Paragraph("<b>Total</b>", body_style),
            Paragraph("", body_style),
            Paragraph("", body_style),
            Paragraph(f"<b>{int(item['total']):,} CDF</b>".replace(",", " "), body_style),
        ])
        detail_table = Table(table_data, colWidths=[30 * mm, 70 * mm, 55 * mm, 32 * mm], repeatRows=1)
        detail_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e0f2fe")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(detail_table)
        story.append(Spacer(1, 4 * mm))
        story.append(_build_signature_footer(body_style))

    if not bulletin["resultats"]:
        story.append(Paragraph(
            "Aucune prestation trouvée pour générer un bulletin de paie.",
            body_style,
        ))

    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer


@login_required
def bulletin_paie_pdf(request):
    form = CalculPaieForm(request.GET or None)
    if not form.is_valid():
        messages.info(request, "Sélectionnez d'abord un mois et une section pour générer le bulletin de paie.")
        return redirect("prestation:bulletin_paie")

    mois = int(form.cleaned_data["mois"])
    section = form.cleaned_data["section"]
    paie_data = _collect_paie_data(mois, section)
    bulletin = {
        "mois": MONTH_LABELS.get(str(mois), str(mois)),
        "section": section,
        "section_label": section.nom or section.code or "SECTION",
        "annee_academique": _get_calcul_annee(),
        "resultats": paie_data["resultats"],
    }
    pdf_buffer = _build_bulletin_pdf(bulletin)
    filename = f"bulletin_paie_{mois}_{section.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def bulletin_paie_individuel_pdf(request, personnel_id):
    form = CalculPaieForm(request.GET or None)
    if not form.is_valid():
        messages.info(request, "Sélectionnez d'abord un mois et une section pour générer le bulletin individuel.")
        return redirect("prestation:etat_paie_mensuel")

    mois = int(form.cleaned_data["mois"])
    section = form.cleaned_data["section"]
    personnel = get_object_or_404(Personnel, pk=personnel_id)
    bulletin_item = _collect_individual_bulletin(personnel, mois, section)
    bulletin = {
        "mois": MONTH_LABELS.get(str(mois), str(mois)),
        "section": section,
        "section_label": section.nom or section.code or "SECTION",
        "annee_academique": _get_calcul_annee(),
        "resultats": [{
            "personnel": personnel,
            "prestations": bulletin_item["prestations"],
            "total": bulletin_item["total_general"],
        }],
        "titre": f"BULLETIN DE PAIE INDIVIDUEL - {personnel.first_name} {personnel.last_name}",
    }
    pdf_buffer = _build_bulletin_pdf(bulletin)
    filename = f"bulletin_paie_{mois}_{section.pk}_{personnel.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _build_fiche_prestations_journaliere_pdf(fiche):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=5 * mm,
        leftMargin=5 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FicheJourTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14.2,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "FicheJourBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.6,
        leading=8.6,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
    )
    center_style = ParagraphStyle(
        "FicheJourCenter",
        parent=body_style,
        alignment=TA_CENTER,
    )

    direction = "DIRECTION DES SYSTEMES D'INFORMATION"
    ecole = "ECOLE INFORMATIQUE DES FINANCES"
    section_label = fiche["section_label"]
    year_text = fiche["annee_academique"].code if fiche.get("annee_academique") else "AUTOMATIQUE"
    story = [
        _build_header_table(body_style, direction, ecole, f"SYSTÈME LMD/{section_label}", "ANNEE ACADEMIQUE", year_text),
        Spacer(1, 4 * mm),
        Paragraph(
            f"<u><b>FICHE DES PRESTATIONS JOURNALIÈRES - {fiche['date_label']}</b></u>",
            title_style,
        ),
        Spacer(1, 1 * mm),
        Paragraph(
            f"Générée le <b>{fiche.get('generated_label', date.today().strftime('%d/%m/%Y'))}</b>",
            ParagraphStyle(
                "FicheJourGenerated",
                parent=body_style,
                fontSize=8,
                leading=9,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#64748b"),
            ),
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            f"Section : <b>{section_label}</b>",
            ParagraphStyle(
                "FicheJourMeta",
                parent=body_style,
                fontSize=8.4,
                leading=10,
                textColor=colors.HexColor("#334155"),
            ),
        ),
        Spacer(1, 3 * mm),
    ]

    table_data = [[
        Paragraph("<b>N°</b>", center_style),
        Paragraph("<b>NOM &amp; PRÉNOM</b>", center_style),
        Paragraph("<b>CATÉGORIE</b>", center_style),
        Paragraph("<b>UE</b>", center_style),
        Paragraph("<b>HEURE DÉBUT</b>", center_style),
        Paragraph("<b>HEURE FIN</b>", center_style),
        Paragraph("<b>CLASSE</b>", center_style),
        Paragraph("<b>LOCAL</b>", center_style),
        Paragraph("<b>SIGNATURE</b>", center_style),
    ]]

    for row in fiche["rows"]:
        table_data.append([
            Paragraph(str(row["numero"]), center_style),
            Paragraph(row["nom_prenom"], body_style),
            Paragraph(row["categorie"], body_style),
            Paragraph(row["ue"], body_style),
            Paragraph(row["heure_debut"], center_style),
            Paragraph(row["heure_fin"], center_style),
            Paragraph(row["classe"], body_style),
            Paragraph(row["local"], body_style),
            Paragraph(" ", body_style),
        ])

    if len(table_data) == 1:
        table_data.append([
            Paragraph("-", center_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
            Paragraph("-", center_style),
            Paragraph("-", center_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
        ])

    table = Table(
        table_data,
        colWidths=[
            10 * mm,
            60 * mm,
            24 * mm,
            22 * mm,
            18 * mm,
            18 * mm,
            25 * mm,
            20 * mm,
            90 * mm,
        ],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#94a3b8")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (4, 1), (5, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(table)
    story.append(Spacer(1, 4 * mm))
    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer


@login_required
def fiche_prestations_journaliere(request):
    form = FichePrestationJournaliereForm(request.GET or None)
    fiche = None
    download_query = ""

    if form.is_valid():
        jour = form.cleaned_data["jour"]
        section = form.cleaned_data["section"]
        semestre = form.cleaned_data["semestre"]
        annee_academique = form.cleaned_data["annee_academique"]
        fiche_data = _collect_fiche_prestations(section, jour, semestre, annee_academique)
        if not fiche_data["lines"]:
            messages.info(request, "Aucune prestation n'a été trouvée pour ce jour, ce semestre, cette année académique et cette section.")

        fiche = {
            "jour": jour,
            "jour_label": fiche_data["day_label"],
            "generated_label": date.today().strftime("%d/%m/%Y"),
            "day_label": fiche_data["day_label"],
            "section": section,
            "section_label": section.nom or section.code or "SECTION",
            "semestre": semestre,
            "annee_academique": annee_academique,
            "rows": fiche_data["lines"],
            "total_lignes": len(fiche_data["lines"]),
        }
        download_query = f"jour={jour}&section={section.pk}&semestre={semestre.pk}&annee_academique={annee_academique.pk}"

    return render(request, "prestation/fiche_prestations_journaliere.html", {
        "form": form,
        "fiche": fiche,
        "download_query": download_query,
    })


@login_required
def fiche_prestations_journaliere_pdf(request):
    form = FichePrestationJournaliereForm(request.GET or None)
    if not form.is_valid():
        messages.info(request, "Sélectionnez d'abord un jour, un semestre, une année académique et une section pour générer la fiche journalière.")
        return redirect("prestation:fiche_prestations_journaliere")

    jour = form.cleaned_data["jour"]
    section = form.cleaned_data["section"]
    semestre = form.cleaned_data["semestre"]
    annee_academique = form.cleaned_data["annee_academique"]
    fiche_data = _collect_fiche_prestations(section, jour, semestre, annee_academique)
    fiche = {
        "jour": jour,
        "jour_label": fiche_data["day_label"],
        "date_label": date.today().strftime("%d/%m/%Y"),
        "generated_label": date.today().strftime("%d/%m/%Y"),
        "day_label": fiche_data["day_label"],
        "section": section,
        "section_label": section.nom or section.code or "SECTION",
        "semestre": semestre,
        "annee_academique": annee_academique,
        "rows": fiche_data["lines"],
    }
    pdf_buffer = _build_fiche_prestations_journaliere_pdf(fiche)
    filename = f"fiche_prestations_{jour}_{section.pk}_{semestre.pk}_{annee_academique.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def etat_paie_mensuel(request):
    annee_academique = _get_calcul_annee()
    form = CalculPaieForm(request.GET or None)
    etat = None
    download_query = ""

    if form.is_valid():
        mois = int(form.cleaned_data["mois"])
        section = form.cleaned_data["section"]
        paie_data = _collect_paie_data(mois, section)
        if paie_data["fallback_used"]:
            messages.warning(
                request,
                "Aucune prestation n'est rattachée à cette section dans les données. L'état affiche donc toutes les prestations du mois sélectionné.",
            )
        elif not paie_data["prestations"]:
            messages.info(request, "Aucune prestation trouvée pour ce mois et cette section.")

        lignes = []
        for index, item in enumerate(paie_data["resultats"], start=1):
            personnel = item["personnel"]
            lignes.append({
                "numero": index,
                "personnel_id": personnel.pk,
                "nom": personnel.last_name,
                "prenom": personnel.first_name,
                "net": item["total"],
            })

        etat = {
            "mois": MONTH_LABELS.get(str(mois), str(mois)),
            "section": section,
            "section_label": section.nom or section.code or "SECTION",
            "annee_academique": annee_academique,
            "lignes": lignes,
            "total_general": paie_data["total_general"],
        }
        download_query = f"mois={mois}&section={section.pk}"

    return render(request, "prestation/etat_paie_mensuel.html", {
        "form": form,
        "etat": etat,
        "annee_academique": annee_academique,
        "download_query": download_query,
    })


def _build_etat_paie_pdf(etat):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "EtatPaieTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14.2,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#475569"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodySmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
    )
    center_style = ParagraphStyle(
        "CenterSmall",
        parent=body_style,
        alignment=TA_CENTER,
    )

    story = []
    direction = "DIRECTION DES SYSTEMES D'INFORMATION"
    ecole = "ECOLE INFORMATIQUE DES FINANCES"
    systeme_affichage = f"SYSTÈME LMD/{etat['section_label']}"
    year_text = etat["annee_academique"].code if etat.get("annee_academique") else "AUTOMATIQUE"
    story.append(_build_header_table(body_style, direction, ecole, systeme_affichage, "ANNEE ACADEMIQUE", year_text))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"<u><b>ETAT DE PAIE MENSUEL - {etat['mois']} {etat['annee_academique'].code if etat.get('annee_academique') else ''}</b></u>",
        title_style,
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Section : <b>{etat['section_label']}</b>",
        ParagraphStyle(
            "EtatMeta",
            parent=body_style,
            fontSize=8.6,
            leading=10.2,
            textColor=colors.HexColor("#334155"),
        ),
    ))
    story.append(Spacer(1, 3 * mm))

    table_data = [[
        Paragraph("<b>N°</b>", center_style),
        Paragraph("<b>NOM</b>", center_style),
        Paragraph("<b>PRENOM</b>", center_style),
        Paragraph("<b>NET A PAYER</b>", center_style),
    ]]
    for ligne in etat["lignes"]:
        table_data.append([
            Paragraph(str(ligne["numero"]), center_style),
            Paragraph(ligne["nom"], body_style),
            Paragraph(ligne["prenom"], body_style),
            Paragraph(f"{int(ligne['net']):,} CDF".replace(",", " "), body_style),
        ])
    table_data.append([
        Paragraph("<b>TOTAL GENERAL</b>", body_style),
        Paragraph("", body_style),
        Paragraph("", body_style),
        Paragraph(f"<b>{int(etat['total_general']):,} CDF</b>".replace(",", " "), body_style),
    ])

    payroll_table = Table(table_data, colWidths=[15 * mm, 55 * mm, 65 * mm, 42 * mm], repeatRows=1)
    payroll_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e0f2fe")),
        ("SPAN", (0, -1), (2, -1)),
        ("ALIGN", (0, -1), (2, -1), "RIGHT"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(payroll_table)
    story.append(Spacer(1, 6 * mm))
    story.append(_build_signature_footer(body_style))

    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer


@login_required
def etat_paie_mensuel_pdf(request):
    form = CalculPaieForm(request.GET or None)
    if not form.is_valid():
        messages.info(request, "Sélectionnez d'abord un mois et une section pour générer l'état de paie.")
        return redirect("prestation:etat_paie_mensuel")

    mois = int(form.cleaned_data["mois"])
    section = form.cleaned_data["section"]
    paie_data = _collect_paie_data(mois, section)
    lignes = []
    for index, item in enumerate(paie_data["resultats"], start=1):
        personnel = item["personnel"]
        lignes.append({
            "numero": index,
            "personnel_id": personnel.pk,
            "nom": personnel.last_name,
            "prenom": personnel.first_name,
            "net": item["total"],
        })
    etat = {
        "mois": MONTH_LABELS.get(str(mois), str(mois)),
        "section": section,
        "section_label": section.nom or section.code or "SECTION",
        "annee_academique": _get_calcul_annee(),
        "lignes": lignes,
        "total_general": paie_data["total_general"],
    }
    pdf_buffer = _build_etat_paie_pdf(etat)
    filename = f"etat_paie_{mois}_{section.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _build_statistiques_enseignement_pdf(statistiques):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "StatsEnseignementTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14.4,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#475569"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "StatsEnseignementBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
    )
    center_style = ParagraphStyle(
        "StatsEnseignementCenter",
        parent=body_style,
        alignment=TA_CENTER,
    )

    section = statistiques["section"]
    annee_academique = statistiques["annee_academique"]
    semestre = statistiques["semestre"]
    date_range_text = _format_statistiques_enseignement_range(statistiques["date_debut"], statistiques["date_fin"])
    story = [
        _build_header_table(
            body_style,
            "DIRECTION DES SYSTEMES D'INFORMATION",
            "ECOLE INFORMATIQUE DES FINANCES",
            "SYSTÈME LMD",
            "SECTION",
            section.nom or section.code or "SECTION",
        ),
        Spacer(1, 4 * mm),
        Paragraph(f"<u><b>STATISTIQUES DES PRESTATIONS {date_range_text}</b></u>", title_style),
        Spacer(1, 2 * mm),
        Paragraph(
            f"Section : <b>{section.nom or section.code or 'SECTION'}</b>",
            ParagraphStyle(
                "StatsSection",
                parent=body_style,
                fontSize=8.6,
                leading=10.4,
                textColor=colors.HexColor("#334155"),
            ),
        ),
        Spacer(1, 3 * mm),
    ]

    table_data = [[
        Paragraph("<b>N°</b>", center_style),
        Paragraph("<b>NOM</b>", center_style),
        Paragraph("<b>UE</b>", center_style),
        Paragraph("<b>NOMBRE DE PRESTATIONS</b>", center_style),
    ]]

    for row in statistiques["rows"]:
        table_data.append([
            Paragraph(str(row["numero"]), center_style),
            Paragraph(row["nom_prenom"], body_style),
            Paragraph(row["ue"], body_style),
            Paragraph(str(row["nombre_prestations"]), center_style),
        ])

    if len(table_data) == 1:
        table_data.append([
            Paragraph("-", center_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
            Paragraph("0", center_style),
        ])

    table = Table(table_data, colWidths=[12 * mm, 78 * mm, 54 * mm, 36 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#94a3b8")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
    ]))
    story.append(table)
    story.append(Spacer(1, 4 * mm))
    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer


@login_required
def statistiques_prestations_enseignement(request):
    form = StatistiquesPrestationEnseignementForm(request.GET or None)
    statistiques = None
    download_query = ""

    if form.is_valid():
        date_debut = form.cleaned_data["date_debut"]
        date_fin = form.cleaned_data["date_fin"]
        section = form.cleaned_data["section"]
        annee_academique = form.cleaned_data["annee_academique"]
        semestre = form.cleaned_data["semestre"]
        stats_data = _collect_statistiques_prestations_enseignement(section, annee_academique, semestre, date_debut, date_fin)

        if not stats_data["rows"]:
            messages.info(request, "Aucune prestation d'enseignement n'a été trouvée pour les critères sélectionnés.")

        statistiques = {
            "section": section,
            "annee_academique": annee_academique,
            "semestre": semestre,
            "date_debut": date_debut,
            "date_fin": date_fin,
            "date_range_label": _format_statistiques_enseignement_range(date_debut, date_fin),
            "rows": stats_data["rows"],
            "total_lignes": stats_data["total_lignes"],
            "total_lignes_stats": stats_data["total_lignes_stats"],
        }
        download_query = f"date_debut={date_debut.isoformat()}&date_fin={date_fin.isoformat()}&section={section.pk}&annee_academique={annee_academique.pk}&semestre={semestre.pk}"

    return render(request, "prestation/statistiques_prestations_enseignement.html", {
        "form": form,
        "statistiques": statistiques,
        "download_query": download_query,
    })


@login_required
def statistiques_prestations_enseignement_pdf(request):
    form = StatistiquesPrestationEnseignementForm(request.GET or None)
    if not form.is_valid():
        messages.info(request, "Sélectionnez d'abord une section, une année académique et un semestre pour générer les statistiques.")
        return redirect("prestation:statistiques_prestations_enseignement")

    date_debut = form.cleaned_data["date_debut"]
    date_fin = form.cleaned_data["date_fin"]
    section = form.cleaned_data["section"]
    annee_academique = form.cleaned_data["annee_academique"]
    semestre = form.cleaned_data["semestre"]
    stats_data = _collect_statistiques_prestations_enseignement(section, annee_academique, semestre, date_debut, date_fin)
    statistiques = {
        "section": section,
        "annee_academique": annee_academique,
        "semestre": semestre,
        "date_debut": date_debut,
        "date_fin": date_fin,
        "rows": stats_data["rows"],
    }
    pdf_buffer = _build_statistiques_enseignement_pdf(statistiques)
    start_text = date_debut.strftime("%d-%m-%Y") if date_debut else "debut"
    end_text = date_fin.strftime("%d-%m-%Y") if date_fin else "fin"
    filename = f"statistiques_enseignement_{start_text}_{end_text}_{section.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _build_pdf(horaire):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "HoraireTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#475569"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodySmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
    )
    center_style = ParagraphStyle(
        "CenterSmall",
        parent=body_style,
        alignment=TA_CENTER,
    )
    right_footer_style = ParagraphStyle(
        "RightFooter",
        parent=body_style,
        alignment=TA_LEFT,
        leading=9,
        spaceBefore=0,
        spaceAfter=0,
    )
    chip_style = ParagraphStyle(
        "Chip",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=7.6,
        leading=8.2,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
    )

    story = []

    logo = _logo_flowable(_asset_path("static", "images", "logoeifi.png"), width_mm=20)
    header_table = Table([[
        logo if logo else Paragraph("EIFI", ParagraphStyle("LogoFallback", parent=body_style, fontName="Helvetica-Bold", fontSize=16, textColor=colors.white)),
        Paragraph(f"<b>{horaire.direction}</b><br/>{horaire.ecole}<br/>{horaire.systeme_affichage}", ParagraphStyle(
            "HeaderTitle",
            parent=body_style,
            fontName="Helvetica-Bold",
            fontSize=11.2,
            leading=13,
            textColor=colors.white,
        )),
        Paragraph(f"<b>ANNEE ACADEMIQUE</b><br/>{horaire.annee_academique.code}", ParagraphStyle(
            "HeaderRight",
            parent=body_style,
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.white,
        )),
    ]], colWidths=[24 * mm, 112 * mm, 40 * mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#0f172a")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#334155")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(f"<u><b>{horaire.titre_document}</b></u>", ParagraphStyle(
        "DocTitle",
        parent=title_style,
        fontSize=14.2,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=8,
    )))
    story.append(Spacer(1, 2 * mm))

    lines = list(
        horaire.lignes.select_related(
            "element_constitutif",
            "element_constitutif__ue",
            "local",
            "professeur",
        ).order_by("jour", "heure_debut", "ordre")
    )
    grouped = _group_lines_by_day(lines)

    table_data = [[
        Paragraph("<b>JOURS</b>", center_style),
        Paragraph("<b>HEURES</b>", center_style),
        Paragraph("<b>UE</b>", center_style),
        Paragraph("<b>LOC</b>", center_style),
    ]]

    span_commands = []
    row_index = 1
    for day in DAY_ORDER:
        day_lines = grouped.get(day, [])
        if not day_lines:
            continue
        start_row = row_index
        for idx, line in enumerate(day_lines):
            day_label = line.get_jour_display().upper() if idx == 0 else ""
            table_data.append([
                Paragraph(f"<b>{day_label}</b>" if day_label else "", body_style),
                Paragraph(f"<b>{_format_time_range(line)}</b>", center_style),
                Paragraph(f"<b>{line.code_affichage}</b>", center_style),
                Paragraph(f"<b>{line.local_affichage}</b>", center_style),
            ])
            row_index += 1
        if len(day_lines) > 1:
            span_commands.append(("SPAN", (0, start_row), (0, start_row + len(day_lines) - 1)))

    if len(table_data) == 1:
        table_data.append([
            Paragraph("-", center_style),
            Paragraph("-", center_style),
            Paragraph("-", center_style),
            Paragraph("-", center_style),
        ])

    schedule_table = Table(table_data, colWidths=[24 * mm, 42 * mm, 74 * mm, 22 * mm], repeatRows=1)
    schedule_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#64748b")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.4),
        ("LEADING", (0, 0), (-1, -1), 9.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#eef2ff")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ] + span_commands))
    story.append(schedule_table)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("<b>INTITULÉS DES UE</b>", ParagraphStyle(
        "LegendTitle",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=9.2,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2,
    )))
    story.append(Spacer(1, 1 * mm))

    legend = _unique_legend_items(lines)
    if legend:
        legend_data = [[
            Paragraph("<b>INTITULES DES UE</b>", center_style),
            Paragraph("<b>TITULAIRE</b>", center_style),
            Paragraph("<b>CODE UE</b>", center_style),
        ]]
        for title, titulaire, code in legend:
            legend_data.append([
                Paragraph(title, body_style),
                Paragraph(titulaire, center_style),
                Paragraph(code, center_style),
            ])
        legend_table = Table(legend_data, colWidths=[96 * mm, 50 * mm, 18 * mm], repeatRows=1)
        legend_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0f2fe")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("FONTSIZE", (0, 0), (-1, -1), 7.6),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(legend_table)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"Le présent horaire a été établi pour la classe <b>{horaire.classe}</b> "
        f"de la filière <b>{horaire.filiere or '-'}</b>.",
        ParagraphStyle(
            "NoteStyle",
            parent=body_style,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#334155"),
        ),
    ))

    if horaire.observation:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(horaire.observation, body_style))

    settings_row = CardSettings.objects.first()
    chief_name = settings_row.training_division_chief_name if settings_row else ""

    footer_block = [
        Paragraph(f"Fait à Kinshasa le {date.today().strftime('%d/%m/%Y')}", right_footer_style),
        Spacer(1, 0.8 * mm),
        Paragraph("<u><b>LE CHEF DE DIVISION FORMATION</b></u>", right_footer_style),
    ]
    if chief_name:
        footer_block.append(Spacer(1, 0.8 * mm))
        footer_block.append(Paragraph(chief_name, right_footer_style))

    footer_table = Table([["", footer_block]], colWidths=[108 * mm, 72 * mm])
    footer_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(Spacer(1, 4 * mm))
    story.append(footer_table)

    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer


@login_required
def horaire_list(request):
    horaires = Horaire.objects.select_related(
        "classe",
        "classe__promotion",
        "classe__promotion__filiere",
        "annee_academique",
        "semestre",
    ).prefetch_related("lignes").all()
    return render(request, "prestation/horaire_list.html", {"horaires": horaires})


@login_required
def horaire_detail(request, pk):
    horaire = get_object_or_404(
        Horaire.objects.select_related(
            "classe",
            "classe__promotion",
            "classe__promotion__filiere",
            "classe__promotion__filiere__section",
            "annee_academique",
            "semestre",
        ).prefetch_related(
            "lignes",
            "lignes__element_constitutif",
            "lignes__local",
            "lignes__professeur",
        ),
        pk=pk,
    )
    lines = list(horaire.lignes.all().order_by("jour", "heure_debut", "ordre"))
    return render(
        request,
        "prestation/horaire_detail.html",
        {
            "horaire": horaire,
            "lines": lines,
            "grouped_lines": _group_lines_by_day(lines),
            "legend_items": _unique_legend_items(lines),
        },
    )


@login_required
def horaire_create(request):
    horaire = Horaire()
    if request.method == "POST":
        form = HoraireForm(request.POST, instance=horaire)
        formset = HoraireLigneFormSet(request.POST, instance=horaire, prefix="lignes")
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                horaire = form.save()
                formset.instance = horaire
                formset.save()
            messages.success(request, "Horaire créé avec succès.")
            return redirect("prestation:horaire_detail", pk=horaire.pk)
    else:
        form = HoraireForm(instance=horaire)
        formset = HoraireLigneFormSet(instance=horaire, prefix="lignes")
    return render(request, "prestation/horaire_form.html", {
        "form": form,
        "formset": formset,
        "title": "Nouvel horaire",
    })


@login_required
def horaire_update(request, pk):
    horaire = get_object_or_404(Horaire, pk=pk)
    if request.method == "POST":
        form = HoraireForm(request.POST, instance=horaire)
        formset = HoraireLigneFormSet(request.POST, instance=horaire, prefix="lignes")
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                horaire = form.save()
                formset.instance = horaire
                formset.save()
            messages.success(request, "Horaire modifié avec succès.")
            return redirect("prestation:horaire_detail", pk=horaire.pk)
    else:
        form = HoraireForm(instance=horaire)
        formset = HoraireLigneFormSet(instance=horaire, prefix="lignes")
    return render(request, "prestation/horaire_form.html", {
        "form": form,
        "formset": formset,
        "title": "Modifier l'horaire",
        "horaire": horaire,
    })


@login_required
def horaire_delete(request, pk):
    horaire = get_object_or_404(Horaire, pk=pk)
    if request.method == "POST":
        horaire.delete()
        messages.success(request, "Horaire supprimé avec succès.")
        return redirect("prestation:horaire_list")
    return render(request, "prestation/horaire_confirm_delete.html", {"horaire": horaire})


@login_required
def horaire_pdf(request, pk):
    horaire = get_object_or_404(
        Horaire.objects.select_related(
            "classe",
            "classe__promotion",
            "classe__promotion__filiere",
            "semestre",
            "annee_academique",
        ).prefetch_related("lignes", "lignes__element_constitutif", "lignes__local", "lignes__professeur"),
        pk=pk,
    )
    pdf_buffer = _build_pdf(horaire)
    filename = f"horaire_{horaire.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
