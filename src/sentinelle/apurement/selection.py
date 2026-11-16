"""Variables de la base apurée : 10 identifiants et 69 variables retenues sur le panel provincial de 2025.

Les autres colonnes du panel restent dans la base de l'étape 03 ; chacune reçoit ici le motif
de son retrait de la base apurée.
"""

from __future__ import annotations

import pandas as pd

from ..transformation.recensement import colonnes as _colonnes_recensement

RECENSEMENT = set(_colonnes_recensement("province").values())

IDENTIFIANTS = ["province_pcode", "province_nom", "region_pcode", "region_nom", "province_ancienne_pcode",
                "province_ancienne_nom", "region_ancienne_pcode", "region_ancienne_nom", "annee_scolaire",
                "methode_passage"]

VARIABLES = [
    # Flux du primaire (la cible de l'année t est la valeur « précédente » de t+1) et effectifs.
    "abandon_primaire_precedent", "redoublement_primaire_precedent", "promotion_primaire_precedente",
    "eleves_primaire", "part_filles_primaire", "part_cp1", "rapport_cm2_cp1", "evolution_eleves_primaire",
    "choc_eleves_primaire",
    # Encadrement et contexte régional de la base principale.
    "eleves_par_maitre_primaire", "eleves_par_salle_primaire", "ips_tbs_primaire_region", "ips_tap_primaire_region",
    "tbs_prescolaire_region", "part_ecoles_primaires_privees_region",
    # Conditions de scolarisation (annuaires du primaire).
    "part_ecoles_primaires_cantine", "part_ecoles_primaires_latrines", "part_ecoles_primaires_eau_potable",
    "part_ecoles_primaires_electricite", "part_eleves_primaire_plus_3km", "part_ecoles_primaires_cycle_incomplet",
    "logements_pour_100_maitres_primaire", "manuels_lecture_par_eleve_primaire", "manuels_calcul_par_eleve_primaire",
    "part_parents_agriculteurs_eleves_primaire", "part_salles_primaire_murs_precaires",
    "part_salles_primaire_toit_precaire", "tba_primaire_province", "tbs_primaire_province", "tns_primaire_province",
    "achevement_primaire_province", "reussite_cep_precedente_province", "deficit_places_pour_100_eleves_primaire",
    "part_eleves_primaire_12_ans_et_plus", "part_entrants_cp1_8_ans_et_plus", "part_enseignantes_primaire",
    "part_enseignants_primaire_debutants", "abandons_primaire_orpaillage_pour_1000_region",
    "abandons_primaire_mariage_grossesse_pour_1000_region",
    # Post-primaire.
    "tba_6e_province", "tbs_post_primaire_province", "achevement_post_primaire_province",
    "parite_tbs_post_primaire_province", "abandon_post_primaire_province", "redoublement_3e_province",
    "ratio_eleves_classe_post_primaire_region", "part_etab_post_primaire_secondaire_publics_electricite_region",
    "part_etab_post_primaire_secondaire_publics_cantine_region", "ecart_achevement_primaire_entree_6e",
    # Recensement de 2019.
    "pauvrete_province", "travail_enfants_7_14_province", "emploi_15_24_province", "chomage_25_64_province",
    "frequentation_post_primaire_province", "frequentation_secondaire_province",
    "parite_scolarisation_primaire_province", "parite_scolarisation_post_primaire_province",
    "parite_scolarisation_secondaire_province", "hors_ecole_6_11_province", "hors_ecole_12_15_province",
    "hors_ecole_16_18_province", "ni_ecole_ni_emploi_15_24_province", "alphabetisation_adultes_province",
    "dependance_demographique_province", "filles_17_ans_mariees_province",
    # Valeurs de la province d'origine et indicateurs.
    "abandon_primaire_precedent_province_origine", "redoublement_primaire_precedent_province_origine",
    "cible_observee", "methode_population",
]
COLONNES = IDENTIFIANTS + VARIABLES


def motif_retrait(colonne: str, colonnes: list[str]) -> str:
    if "suivant" in colonne:
        return "année t+1 : la même série est gardée sous sa forme « précédente »"
    if colonne.endswith("_region") and colonne.replace("taux_achevement_primaire", "achevement_primaire")[:-7] + \
            "_province" in colonnes:
        return "valeur régionale doublée par la valeur provinciale"
    if colonne in ("statut_cible", "rupture_cible", "date_deplaces", "eleves_primaire_precedent",
                   "promotion_primaire_precedente_province_origine"):
        return "identifiant, statut ou doublon d'une variable gardée"
    if colonne.startswith(("deplaces", "ecoles_primaires_fermees", "eleves_primaire_touches", "etablissements_fermes",
                           "eleves_affectes")):
        return "crise : série courte (2019 à 2023), gardée dans la base de l'étape 03"
    if colonne in RECENSEMENT or colonne in ("consommation_par_personne_province", "gini_province",
                                             "rapport_q90_q10_province"):
        return "indicateur du recensement de 2019 ou de consommation non retenu"
    if colonne.startswith(("population", "moins_15", "age_15_64", "plus_64", "enfants_", "jeunes_", "rapport_dependance",
                           "part_moins_15", "croissance_enfants")):
        return "population annuelle : complète, gardée dans la base de l'étape 03"
    return "hors du périmètre retenu pour la base apurée"


def selectionner(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Base réduite aux colonnes retenues, et table des colonnes retirées avec leur motif."""
    manquantes = [c for c in COLONNES if c not in panel]
    if manquantes:
        raise KeyError(f"colonnes absentes du panel : {manquantes}")
    retirees = pd.DataFrame([{"variable": c, "motif": motif_retrait(c, list(panel.columns))}
                             for c in panel.columns if c not in COLONNES])
    return panel[COLONNES].copy(), retirees
