from decimal import Decimal

from django.db.models import Sum

from .models import EnveloppeBudgetaire, PaieMensuelle, Prestation

MONTH_LABELS = {
    1: "Janvier",
    2: "Février",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Août",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Décembre",
}


def get_month_label(mois):
    return MONTH_LABELS.get(int(mois), str(mois))


def get_total_prestations_mois(annee, mois):
    total = Prestation.objects.filter(
        date_prestation__year=annee,
        date_prestation__month=mois,
    ).aggregate(total=Sum("montant"))["total"]
    return Decimal(total or 0)


def get_budget_context(annee, mois):
    annee = int(annee)
    mois = int(mois)
    enveloppe = EnveloppeBudgetaire.objects.filter(annee=annee, mois=mois).first()
    total_engage = get_total_prestations_mois(annee, mois)
    paie_validee = None
    if enveloppe:
        try:
            paie_validee = enveloppe.paie_validee
        except PaieMensuelle.DoesNotExist:
            paie_validee = None

    if not enveloppe:
        return {
            "annee": annee,
            "mois": mois,
            "mois_label": get_month_label(mois),
            "enveloppe": None,
            "montant_enveloppe": Decimal("0"),
            "total_engage": total_engage,
            "solde_disponible": Decimal("0"),
            "depasse": True,
            "paie_validee": paie_validee,
            "deja_validee": False,
            "deja_cloturee": False,
            "peut_valider": False,
            "peut_cloturer": False,
            "total_paye": total_engage,
            "message": "Aucune enveloppe budgétaire n'est définie pour cette période.",
        }

    montant_enveloppe = Decimal(enveloppe.montant)
    solde_disponible = montant_enveloppe - total_engage
    depasse = total_engage > montant_enveloppe
    deja_validee = paie_validee is not None

    context = {
        "annee": annee,
        "mois": mois,
        "mois_label": get_month_label(mois),
        "enveloppe": enveloppe,
        "montant_enveloppe": montant_enveloppe,
        "total_engage": total_engage,
        "solde_disponible": solde_disponible,
        "depasse": depasse,
        "paie_validee": paie_validee,
        "deja_validee": deja_validee,
        "peut_valider": not deja_validee and not depasse,
    }

    context["deja_cloturee"] = deja_validee
    context["peut_cloturer"] = context["peut_valider"]
    context["total_paye"] = total_engage

    if deja_validee:
        context["message"] = "La paie mensuelle de cette période est déjà clôturée."
    elif depasse:
        context["message"] = (
            f"Le total des prestations ({int(total_engage):,} CDF) dépasse l'enveloppe budgétaire "
            f"({int(montant_enveloppe):,} CDF). Solde disponible : {int(solde_disponible):,} CDF."
        ).replace(",", " ")
    else:
        context["message"] = (
            f"Solde disponible : {int(solde_disponible):,} CDF "
            f"(enveloppe {int(montant_enveloppe):,} CDF − engagé {int(total_engage):,} CDF)."
        ).replace(",", " ")

    return context


def is_paie_mois_cloturee(annee, mois):
    enveloppe = EnveloppeBudgetaire.objects.filter(annee=int(annee), mois=int(mois)).first()
    if not enveloppe:
        return False
    return PaieMensuelle.objects.filter(enveloppe=enveloppe).exists()


def assert_mois_non_cloture(annee, mois):
    if is_paie_mois_cloturee(annee, mois):
        raise ValueError(
            f"La paie de {get_month_label(mois)} {annee} est clôturée. "
            "Aucune saisie ni modification n'est autorisée pour ce mois."
        )


def assert_prestation_modifiable(date_prestation):
    assert_mois_non_cloture(date_prestation.year, date_prestation.month)


def cloturer_paie_mensuelle(annee, mois, user):
    budget = get_budget_context(annee, mois)
    if not budget["enveloppe"]:
        raise ValueError(budget["message"])
    if budget["deja_cloturee"]:
        raise ValueError("La paie de ce mois est déjà clôturée.")
    if budget["depasse"]:
        raise ValueError(budget["message"])

    paie = PaieMensuelle.objects.create(
        enveloppe=budget["enveloppe"],
        montant_total_valide=budget["total_engage"],
        valide_par=user if user and user.is_authenticated else None,
    )
    return paie, budget


def valider_paie_mensuelle(annee, mois, user):
    return cloturer_paie_mensuelle(annee, mois, user)
