"""Étape 03 : transformation des tables nettoyées en tables d'analyse."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from .. import config
from .panel import SEUIL_RUPTURE, construire_panel, construire_panel_mensuel

SORTIE = config.DONNEES / "03_transformation"

# Rôle, description, source de chaque variable de la table d'analyse.
VARIABLES = {
    "province_ancienne_pcode": ("identifiant", "Code de la province (ancien découpage, 45 provinces)", "COD-AB"),
    "province_ancienne_nom": ("identifiant", "Nom de la province", "OpenStreetMap (HOT)"),
    "region_ancienne_pcode": ("identifiant", "Code de la région (ancien découpage)", "COD-AB"),
    "region_ancienne_nom": ("identifiant", "Nom de la région", "OpenStreetMap (HOT)"),
    "provinces_actuelles": ("identifiant", "Provinces du découpage de 2025 issues de la province", "COD-AB"),
    "annee_scolaire": ("identifiant", "Année scolaire t", ""),
    "abandon_brut_suivant": ("cible (brute)", "Abandon apparent du cycle CP1-CM1 entre t et t+1, en %", "DGESS, tableau VIII.3"),
    "abandon_suivant": ("cible", "Abandon entre t et t+1, en % ; vide en cas de rupture de scolarisation ou pour la dernière année", "DGESS, tableau VIII.3"),
    "statut_cible": ("cible", "abandon observé, rupture de scolarisation ou à prévoir", "calculs des auteurs"),
    "rupture_cible": ("cible", f"Vrai si les effectifs varient de plus de {SEUIL_RUPTURE:.0%} entre t et t+1", "DGESS, tableau VIII.3"),
    "evolution_effectifs_suivante": ("cible (contexte)", "Évolution des effectifs entre t et t+1 ; sert à repérer les ruptures, jamais comme variable explicative", "DGESS, tableau VIII.3"),
    "effectif_suivant": ("cible (contexte)", "Effectif total en t+1 ; jamais comme variable explicative", "DGESS, tableau VIII.3"),
    "abandon_precedent": ("explicative", "Abandon entre t-1 et t, en %", "DGESS, tableau VIII.3"),
    "redoublement_precedent": ("explicative", "Redoublement entre t-1 et t, en %", "DGESS, tableau VIII.3"),
    "promotion_precedente": ("explicative", "Promotion entre t-1 et t, en %", "DGESS, tableau VIII.3"),
    "effectif": ("explicative", "Effectif total du primaire en t", "DGESS, tableau VIII.3"),
    "effectif_precedent": ("explicative", "Effectif total en t-1", "DGESS, tableau VIII.3"),
    "evolution_effectifs": ("explicative", "Évolution des effectifs entre t-1 et t", "DGESS, tableau VIII.3"),
    "choc_effectifs": ("explicative", f"Vrai si les effectifs ont varié de plus de {SEUIL_RUPTURE:.0%} entre t-1 et t", "DGESS, tableau VIII.3"),
    "part_filles": ("explicative", "Part des filles dans l'effectif ; vide quand la répartition publiée est invraisemblable", "DGESS, tableau VIII.3"),
    "part_cp1": ("explicative", "Part du CP1 dans l'effectif", "DGESS, tableau VIII.3"),
    "rapport_cm2_cp1": ("explicative", "Effectif du CM2 rapporté à celui du CP1", "DGESS, tableau VIII.3"),
    "eleves_par_maitre": ("explicative", "Élèves par maître chargé de cours, public et privé", "DGESS, tableau I.1"),
    "eleves_par_salle": ("explicative", "Élèves par salle de classe, public et privé", "DGESS, tableau I.1"),
    "part_eleves_prive": ("explicative", "Part des élèves scolarisés dans le privé", "DGESS, tableau I.1"),
    "deplaces": ("explicative", "Déplacés internes accueillis dans la province, dernière situation connue au 31 décembre de l'année de rentrée", "SP/CONASUR"),
    "date_deplaces": ("qualité", "Date de la situation des déplacés retenue", "SP/CONASUR"),
    "deplaces_pour_100_eleves": ("explicative", "Déplacés accueillis pour 100 élèves inscrits", "SP/CONASUR ; DGESS"),
    "ecoles_fermees_province": ("explicative", "Écoles primaires fermées, moyenne des rapports fiables de l'année scolaire", "ST-ESU"),
    "eleves_touches_province": ("explicative", "Élèves des écoles primaires fermées, moyenne des rapports fiables de l'année", "ST-ESU"),
    "ecoles_fermees_region": ("explicative", "Établissements fermés dans la région (tous ordres), moyenne des rapports de l'année", "ST-ESU"),
    "eleves_affectes_region": ("explicative", "Élèves affectés par les fermetures dans la région, moyenne des rapports de l'année", "ST-ESU"),
}

# Relations entre tables, pour le schéma de la base (rôle architecte).
RELATIONS = [
    ("panel_province_annee", "province_ancienne_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("panel_province_annee", "region_ancienne_pcode", "region_ancienne", "region_ancienne_pcode", "plusieurs à un"),
    ("panel_mensuel_province", "province_ancienne_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("province", "province_ancienne_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un (2 provinces scindées)"),
    ("commune", "province_ancienne_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("commune", "province_pcode", "province", "province_pcode", "plusieurs à un"),
    ("fait_effectifs_retenus", "entite_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("fait_offre_province", "entite_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("fait_flux_publie", "entite_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("fait_esu_province", "province_ancienne_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("fait_esu_region", "region_ancienne_pcode", "region_ancienne", "region_ancienne_pcode", "plusieurs à un"),
    ("fait_pdi_commune", "commune_pcode", "commune", "commune_pcode", "plusieurs à un"),
]


def dictionnaire(panel: pd.DataFrame) -> pd.DataFrame:
    lignes = []
    for colonne in panel.columns:
        role, description, source = VARIABLES.get(colonne, ("", "", ""))
        renseignees = panel[colonne].notna()
        annees = panel.loc[renseignees, "annee_scolaire"]
        lignes.append({"variable": colonne, "role": role, "description": description, "source": source,
                       "part_manquante": round(1 - renseignees.mean(), 3),
                       "premiere_annee": annees.min() if len(annees) else "",
                       "derniere_annee": annees.max() if len(annees) else ""})
    return pd.DataFrame(lignes)


def controles(panel: pd.DataFrame, mensuel: pd.DataFrame, dico: pd.DataFrame) -> pd.DataFrame:
    cles = ["province_ancienne_pcode", "annee_scolaire"]
    explicatives = dico.loc[dico["role"] == "explicative", "variable"]
    interdites = {"abandon_brut_suivant", "abandon_suivant", "evolution_effectifs_suivante", "effectif_suivant"}
    statuts = panel["statut_cible"].value_counts()
    contours = gpd.read_file(config.BASE_GEOPACKAGE, layer="province", engine="pyogrio")
    resultats = [
        ("une_ligne_par_province_et_annee", not panel.duplicated(cles).any() and len(panel) == 45 * panel["annee_scolaire"].nunique(),
         f"{len(panel)} lignes = 45 provinces × {panel['annee_scolaire'].nunique()} années, sans doublon"),
        ("cible_renseignee", statuts.get("abandon observé", 0) >= 300,
         ", ".join(f"{k} : {v}" for k, v in statuts.items())),
        ("aucune_variable_explicative_venant_du_futur", not (set(explicatives) & interdites),
         "les variables de t+1 servent seulement à définir la cible"),
        ("toutes_les_variables_decrites", (dico["role"] != "").all(),
         f"{len(dico)} variables décrites" if (dico["role"] != "").all()
         else "sans description : " + ", ".join(dico.loc[dico["role"] == "", "variable"])),
        ("jointure_carte_2025", set(panel["province_ancienne_pcode"]) == set(contours["province_ancienne_pcode"]),
         f"les 45 provinces du panel couvrent les {len(contours)} provinces de 2025"),
        ("panel_mensuel_sans_doublon", not mensuel.duplicated(["province_ancienne_pcode", "mois"]).any(),
         f"{len(mensuel)} lignes, {mensuel['mois'].nunique()} mois ({mensuel['mois'].min()} à {mensuel['mois'].max()})"),
    ]
    return pd.DataFrame(resultats, columns=["controle", "conforme", "detail"])


def executer_transformation() -> dict[str, pd.DataFrame]:
    sortie = config.verifier_ecriture(SORTIE)
    sortie.mkdir(parents=True, exist_ok=True)
    panel = construire_panel()
    mensuel = construire_panel_mensuel()
    dico = dictionnaire(panel)
    relations = pd.DataFrame(RELATIONS, columns=["table", "cle", "table_liee", "cle_liee", "cardinalite"])
    resultat = {"panel_province_annee": panel, "panel_mensuel_province": mensuel, "dictionnaire_variables_modele": dico,
                "schema_relations": relations, "controles_transformation": controles(panel, mensuel, dico)}
    for nom, table in resultat.items():
        table.to_csv(sortie / f"{nom}.csv", sep=config.SEPARATEUR, encoding=config.ENCODAGE_SORTIE, index=False)
    return resultat
