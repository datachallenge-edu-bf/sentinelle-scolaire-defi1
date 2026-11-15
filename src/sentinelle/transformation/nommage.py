"""Noms publiés des variables des panels et ordre d'enseignement de chacune.

La cible et presque toutes les variables du panel portent sur le primaire, sans le dire
(« effectif », « abandon_suivant ») ; les variables ajoutées ensuite nomment leur ordre
(« tbs_post_primaire_province »). À la publication, chaque variable scolaire nomme l'ordre
d'enseignement qu'elle décrit, avec un vocabulaire fixe :

    prescolaire, primaire (CP1 à CM2), post_primaire (6e à 3e), secondaire (2nde à
    terminale), post_primaire_secondaire (6e à terminale), non_formelle

Une variable du recensement qui mesure la scolarisation d'un groupe d'âge relève de l'ordre de
cet âge (6-11 ans hors de l'école : primaire ; 12-15 ans : post-primaire). Les variables qui
ne décrivent pas l'école (pauvreté, équipement des ménages, déplacés, consommation) relèvent
du contexte. Les écoles fermées des synthèses régionales du ST-ESU couvrent tous les ordres :
leur nom le dit.

Le calcul, les contrôles et le futur modèle gardent les noms internes ; les tables écrites,
leurs métadonnées et le classeur de la base finale portent les noms publiés.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

_CIBLES = {"abandon_suivant": "abandon_primaire_suivant", "abandon_brut_suivant": "abandon_primaire_brut_suivant",
           "abandon_precedent": "abandon_primaire_precedent", "redoublement_precedent": "redoublement_primaire_precedent",
           "promotion_precedente": "promotion_primaire_precedente"}

NOMS_PUBLIES = {
    **_CIBLES,
    **{f"{a}_province_origine": f"{n}_province_origine" for a, n in _CIBLES.items()},
    "effectif": "eleves_primaire", "effectif_precedent": "eleves_primaire_precedent",
    "effectif_suivant": "eleves_primaire_suivant", "evolution_effectifs": "evolution_eleves_primaire",
    "evolution_effectifs_suivante": "evolution_eleves_primaire_suivante", "choc_effectifs": "choc_eleves_primaire",
    "part_filles": "part_filles_primaire", "eleves_par_maitre": "eleves_par_maitre_primaire",
    "eleves_par_salle": "eleves_par_salle_primaire", "part_eleves_prive": "part_eleves_primaire_prive",
    "deplaces_pour_100_eleves": "deplaces_pour_100_eleves_primaire",
    "ecoles_fermees_province": "ecoles_primaires_fermees_province",
    "eleves_touches_province": "eleves_primaire_touches_province",
    "ecoles_fermees_region": "etablissements_fermes_tous_ordres_region",
    "eleves_affectes_region": "eleves_affectes_tous_ordres_region",
    "tba_region": "tba_primaire_region", "tbs_region": "tbs_primaire_region",
    "taux_achevement_region": "taux_achevement_primaire_region", "ips_tbs_region": "ips_tbs_primaire_region",
    "ips_tap_region": "ips_tap_primaire_region", "part_ecoles_privees_region": "part_ecoles_primaires_privees_region",
    "grande_section_province": "grande_section_prescolaire_province",
    "adolescents_non_formelle_pour_1000_eleves": "adolescents_non_formelle_pour_1000_eleves_primaire",
    "part_ecoles_cantine": "part_ecoles_primaires_cantine", "part_ecoles_latrines": "part_ecoles_primaires_latrines",
    "part_ecoles_eau_potable": "part_ecoles_primaires_eau_potable",
    "part_ecoles_electricite": "part_ecoles_primaires_electricite",
    "part_eleves_plus_3km": "part_eleves_primaire_plus_3km",
    "part_ecoles_cycle_incomplet": "part_ecoles_primaires_cycle_incomplet",
    "logements_pour_100_maitres": "logements_pour_100_maitres_primaire",
    "manuels_lecture_par_eleve": "manuels_lecture_par_eleve_primaire",
    "manuels_calcul_par_eleve": "manuels_calcul_par_eleve_primaire",
    "part_parents_agriculteurs": "part_parents_agriculteurs_eleves_primaire",
    "part_salles_murs_precaires": "part_salles_primaire_murs_precaires",
    "part_salles_toit_precaire": "part_salles_primaire_toit_precaire",
    "part_salles_recentes": "part_salles_primaire_recentes",
    "tba_province": "tba_primaire_province", "tbs_province": "tbs_primaire_province",
    "tns_province": "tns_primaire_province", "ecart_tbs_filles_garcons": "ecart_tbs_primaire_filles_garcons",
    "achevement_province": "achevement_primaire_province",
    "deficit_places_pour_100_eleves": "deficit_places_pour_100_eleves_primaire",
    "part_eleves_12_ans_et_plus": "part_eleves_primaire_12_ans_et_plus",
    "part_enseignantes": "part_enseignantes_primaire", "part_enseignants_debutants": "part_enseignants_primaire_debutants",
    "abandons_orpaillage_pour_1000_region": "abandons_primaire_orpaillage_pour_1000_region",
    "abandons_mariage_grossesse_pour_1000_region": "abandons_primaire_mariage_grossesse_pour_1000_region",
    "part_etab_secondaires_publics_electricite_region": "part_etab_post_primaire_secondaire_publics_electricite_region",
    "part_etab_secondaires_publics_cantine_region": "part_etab_post_primaire_secondaire_publics_cantine_region",
    "ecart_achevement_entree_6e": "ecart_achevement_primaire_entree_6e",
    "parite_scolarisation_province": "parite_scolarisation_primaire_province",
    # Panel régional (base principale).
    "tba": "tba_primaire", "tba_filles": "tba_primaire_filles", "tba_garcons": "tba_primaire_garcons",
    "tbs": "tbs_primaire", "tbs_filles": "tbs_primaire_filles", "tbs_garcons": "tbs_primaire_garcons",
    "taux_achevement": "taux_achevement_primaire", "taux_achevement_filles": "taux_achevement_primaire_filles",
    "taux_achevement_garcons": "taux_achevement_primaire_garcons", "ips_tba": "ips_tba_primaire",
    "ips_tbs": "ips_tbs_primaire", "ips_tap": "ips_tap_primaire", "part_ecoles_privees": "part_ecoles_primaires_privees",
    "eleves_par_ecole": "eleves_primaire_par_ecole",
}
ANCIENS = {nouveau: ancien for ancien, nouveau in NOMS_PUBLIES.items()}

# (motif sur le nom publié, ordre), du plus précis au plus général.
REGLES = [
    (r"^(province|region|commune)(_ancienne)?_(pcode|nom)$|^annee_scolaire$|^methode_passage$|^statut_cible$"
     r"|^methode_population$"
     r"|^rupture_cible$|^cible_observee$|^date_deplaces$|^provinces_actuelles$|^mois$", "identifiant"),
    (r"^enfants_3_5", "préscolaire"),
    (r"^(enfants_5|enfants_6_11)", "primaire"),
    (r"^enfants_12_15", "post-primaire"),
    (r"^jeunes_16_18", "secondaire"),
    (r"tous_ordres", "tous ordres"),
    (r"post_primaire_secondaire", "post-primaire et secondaire"),
    (r"prescola|section", "préscolaire"),
    (r"non_formelle", "non formel"),
    (r"post_primaire|(^|_)(6e|3e)(_|$)|hors_ecole_12_15", "post-primaire"),
    (r"secondaire|hors_ecole_16_18", "secondaire"),
    (r"primaire|(^|_)cp1(_|$)|cm2|(^|_)cep(_|$)|hors_ecole_6_11", "primaire"),
]


def ordre_enseignement(nom: str) -> str:
    return next((o for motif, o in REGLES if re.search(motif, nom)), "contexte")


def _avec_ordre(texte: str, nom: str) -> str:
    if ordre_enseignement(nom) == "primaire" and "primaire" not in texte.lower() and not re.search(
            r"CP1|CM2|CEP", texte):
        return f"{texte} (primaire)"
    return texte


def etendre(fiches: dict, variables: dict, variables_region: dict) -> None:
    """Ajoute aux dictionnaires de métadonnées une entrée pour chaque nom publié."""
    for ancien, nouveau in NOMS_PUBLIES.items():
        if ancien in fiches and nouveau not in fiches:
            libelle, *reste = fiches[ancien]
            fiches[nouveau] = (_avec_ordre(libelle, nouveau), *reste)
        if ancien in variables and nouveau not in variables:
            role, description, source = variables[ancien]
            variables[nouveau] = (role, _avec_ordre(description, nouveau), source)
        if ancien in variables_region and nouveau not in variables_region:
            variables_region[nouveau] = _avec_ordre(variables_region[ancien], nouveau)


def publier(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    sortie = {}
    for nom, table in tables.items():
        publiee = table.rename(columns=NOMS_PUBLIES)
        if publiee.columns.duplicated().any():
            raise ValueError(f"{nom} : noms publiés en double")
        sortie[nom] = publiee
    return sortie


def classeur_base_finale(tables: dict[str, pd.DataFrame], dictionnaire: pd.DataFrame, chemin: Path) -> list[str]:
    """Pour chaque panel : un onglet global (le panel entier) et un onglet par ordre d'enseignement.

    Un onglet d'ordre reprend les identifiants, les variables de l'ordre et le contexte du
    territoire (pauvreté, ménages, déplacés, consommation), pour se lire seul.
    """
    ordres = ["primaire", "préscolaire", "non formel", "post-primaire", "secondaire", "post-primaire et secondaire",
              "tous ordres", "contexte"]
    courts = {"primaire": "primaire", "préscolaire": "prescolaire", "non formel": "non_formel",
              "post-primaire": "post_primaire", "secondaire": "secondaire",
              "post-primaire et secondaire": "post_prim_second", "tous ordres": "tous_ordres", "contexte": "contexte"}
    onglets = []
    with pd.ExcelWriter(chemin, engine="openpyxl") as classeur:
        pd.DataFrame({"Sentinelle Scolaire : base finale, découpage administratif de 2025": [
            "Pour chaque panel (province de 2025, région de 2025) : un onglet global, le panel entier, puis un onglet "
            "par ordre d'enseignement.",
            "Chaque onglet d'ordre reprend les identifiants (codes et noms de 2025 et de l'ancien découpage, année, "
            "méthode de passage, statut de la cible), les variables de l'ordre, puis le contexte du territoire.",
            "La cible du modèle, abandon_primaire_suivant, est dans l'onglet du primaire ; cible_observee indique les "
            "lignes utilisables pour l'entraînement.",
            "L'onglet « variables » décrit chaque variable et son ordre d'enseignement."]}).to_excel(
            classeur, sheet_name="lisez-moi", index=False)
        for nom, table in tables.items():
            prefixe = nom.replace("panel_", "").replace("_2025", "").replace("_annee", "")
            identifiants = [c for c in table.columns if ordre_enseignement(c) == "identifiant"]
            contexte = [c for c in table.columns if ordre_enseignement(c) == "contexte"]
            table.to_excel(classeur, sheet_name=f"{prefixe}_global"[:31], index=False)
            onglets.append(f"{prefixe}_global")
            for o in ordres:
                colonnes = [c for c in table.columns if ordre_enseignement(c) == o]
                if colonnes and o != "contexte":
                    onglet = f"{prefixe}_{courts[o]}"[:31]
                    table[identifiants + colonnes + contexte].to_excel(classeur, sheet_name=onglet, index=False)
                    onglets.append(onglet)
        variables = dictionnaire[dictionnaire["table"].isin(tables)].copy()
        if "ordre_enseignement" not in variables:
            variables.insert(2, "ordre_enseignement", variables["variable"].map(ordre_enseignement))
        variables.to_excel(classeur, sheet_name="variables", index=False)
    return onglets
