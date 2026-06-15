"""Génération et validation des matricules étudiants (ex. 2026R001)."""

from collections import defaultdict

from academics.models import AnneeAcademique

FILIERE_MATRICULE_SUFFIX = {
    'CSI': 'C',
    'RX': 'R',
}

MATRICULE_REGEX = r'^\d{4}[RC]\d{3}$'
MATRICULE_HELP = "Format : année + C (conception) ou R (réseaux) + n° à 3 chiffres (ex. 2026R001)"


def matricule_year_default(annee=None):
    """Année affichée dans le matricule (ex. 2026 pour 2025-2026)."""
    annee = annee or AnneeAcademique.get_active()
    if not annee:
        return None
    return annee.annee_fin


def format_matricule(year, suffix, order):
    return f"{int(year)}{suffix}{int(order):03d}"


def suffix_for_filiere(filiere_code):
    suffix = FILIERE_MATRICULE_SUFFIX.get(filiere_code)
    if not suffix:
        raise ValueError(f"Filière non prise en charge pour le matricule : {filiere_code}")
    return suffix


def build_matricule_assignments_from_lists(year, csi_rows, rx_rows, find_student):
    """
    Numérotation selon l'ordre des listes officielles (Conception / Réseaux).
    find_student(row) -> Student | None
    """
    assignments = []
    assigned = set()

    for idx, row in enumerate(csi_rows, start=1):
        student = find_student(row)
        if student and student.pk not in assigned:
            assignments.append((student, format_matricule(year, 'C', idx)))
            assigned.add(student.pk)

    for idx, row in enumerate(rx_rows, start=1):
        student = find_student(row)
        if student and student.pk not in assigned:
            assignments.append((student, format_matricule(year, 'R', idx)))
            assigned.add(student.pk)

    return assignments


def build_matricule_assignments(annee, year=None):
    """
    Retourne [(student, nouveau_matricule), …] pour l'année académique donnée.
    Suffixe selon la filière d'inscription (CSI → C, RX → R), ordre alphabétique.
    """
    from students.models import Inscription

    year = year or matricule_year_default(annee)
    if not year:
        raise ValueError("Année de matricule introuvable.")

    inscriptions = (
        Inscription.objects.filter(
            annee_academique=annee,
            classe__isnull=False,
            classe__promotion__filiere__isnull=False,
        )
        .select_related('etudiant', 'classe__promotion__filiere')
        .order_by('classe__promotion__filiere__code', 'etudiant__nom', 'etudiant__prenom')
    )

    by_filiere = defaultdict(list)
    seen = set()
    for ins in inscriptions:
        filiere_code = ins.classe.promotion.filiere.code
        if filiere_code not in FILIERE_MATRICULE_SUFFIX:
            continue
        if ins.etudiant_id in seen:
            continue
        seen.add(ins.etudiant_id)
        by_filiere[filiere_code].append(ins.etudiant)

    assignments = []
    for filiere_code in sorted(FILIERE_MATRICULE_SUFFIX.keys()):
        suffix = FILIERE_MATRICULE_SUFFIX[filiere_code]
        students = by_filiere.get(filiere_code, [])
        students.sort(key=lambda s: (s.nom.upper(), s.prenom.upper()))
        for order, student in enumerate(students, start=1):
            assignments.append((student, format_matricule(year, suffix, order)))

    return assignments


def apply_matricule_assignments(assignments, update_email=False):
    """Applique les matricules (phase temporaire pour éviter les doublons uniques)."""
    from students.models import Student

    if not assignments:
        return 0

    for i, (student, _new) in enumerate(assignments):
        Student.objects.filter(pk=student.pk).update(numero_etudiant=f"TMPMAT{i:05d}")

    updated = 0
    for student, new_numero in assignments:
        fields = {'numero_etudiant': new_numero}
        if update_email:
            fields['email'] = f"{new_numero.lower()}@student.ecore.local"
        Student.objects.filter(pk=student.pk).update(**fields)
        updated += 1

    return updated
