"""Tous les indicateurs de la base apurée, pour l'assistant : valeur par province, repères nationaux, lien avec le
risque prévu.

Le modèle d'explication ne garde que les variables qui améliorent la prédiction ; les autres (pauvreté, cantines,
eau, distance à l'école, mariage précoce…) restent utiles pour décrire une province. Pour chacune, on donne la
valeur la plus récente de la province, la médiane des provinces, le rang, et la corrélation de rang (Spearman)
entre l'indicateur et le taux d'abandon prévu : une association entre provinces, pas un effet.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from donnees import DONNEES, DONNEES_APPLI as D, fr, nom_variable

DICTIONNAIRE = DONNEES / "03_transformation" / "dictionnaire_variables_modele.csv"
METADONNEES = DONNEES / "03_transformation" / "metadonnees" / "dictionnaire_bases_modele.csv"
MOTS_CROISSANT = ["manqu", "moins", "plus faible", "plus bas", "faibles", "peu de", "pas de", "sans "]
NON_INDICATEURS = {"province_pcode", "province_nom", "region_pcode", "region_nom", "province_ancienne_pcode",
                   "province_ancienne_nom", "region_ancienne_pcode", "region_ancienne_nom", "annee_scolaire",
                   "methode_passage", "cible_observee", "methode_population", "nb_valeurs_imputees", "statut_imputation",
                   "abandon_primaire_precedent_province_origine", "redoublement_primaire_precedent_province_origine",
                   "choc_eleves_primaire"}

# Mots de la question → indicateurs (mode hors ligne ; le mode Gemini choisit lui-même dans le catalogue).
MOTS_CLES = {
    "pauvre": ["pauvrete_province"], "pauvrete": ["pauvrete_province"],
    "cantine": ["part_ecoles_primaires_cantine", "part_etab_post_primaire_secondaire_publics_cantine_region"],
    "eau": ["part_ecoles_primaires_eau_potable"], "latrine": ["part_ecoles_primaires_latrines"],
    "electri": ["part_ecoles_primaires_electricite"], "distance": ["part_eleves_primaire_plus_3km"],
    "3 km": ["part_eleves_primaire_plus_3km"], "loin": ["part_eleves_primaire_plus_3km"],
    "maitre": ["eleves_par_maitre_primaire"], "enseignant": ["eleves_par_maitre_primaire", "part_enseignantes_primaire",
                                                               "part_enseignants_primaire_debutants"],
    "salle": ["eleves_par_salle_primaire", "deficit_places_pour_100_eleves_primaire"],
    "place": ["deficit_places_pour_100_eleves_primaire"], "table": ["deficit_places_pour_100_eleves_primaire"],
    "manuel": ["manuels_lecture_par_eleve_primaire", "manuels_calcul_par_eleve_primaire"],
    "mariage": ["filles_17_ans_mariees_province", "abandons_primaire_mariage_grossesse_pour_1000_region"],
    "grossesse": ["abandons_primaire_mariage_grossesse_pour_1000_region"],
    "orpaillage": ["abandons_primaire_orpaillage_pour_1000_region"], "mine": ["abandons_primaire_orpaillage_pour_1000_region"],
    "travail": ["travail_enfants_7_14_province"], "alphabet": ["alphabetisation_adultes_province"],
    "chomage": ["chomage_25_64_province"], "emploi": ["emploi_15_24_province", "ni_ecole_ni_emploi_15_24_province"],
    "hors de l'ecole": ["hors_ecole_6_11_province", "hors_ecole_12_15_province", "hors_ecole_16_18_province"],
    "non scolarise": ["hors_ecole_6_11_province", "hors_ecole_12_15_province"],
    "redoubl": ["redoublement_primaire_precedent"], "achevement": ["achevement_primaire_province"],
    "prive": ["part_ecoles_primaires_privees_region"], "prescolaire": ["tbs_prescolaire_region"],
    "logement": ["logements_pour_100_maitres_primaire"], "precaire": ["part_salles_primaire_murs_precaires",
                                                                      "part_salles_primaire_toit_precaire"],
    "dependance": ["dependance_demographique_province"], "agricult": ["part_parents_agriculteurs_eleves_primaire"],
    "effectif": ["eleves_primaire", "evolution_eleves_primaire"], "cycle incomplet": ["part_ecoles_primaires_cycle_incomplet"],
    "age": ["part_eleves_primaire_12_ans_et_plus", "part_entrants_cp1_8_ans_et_plus"],
    "parite": ["parite_scolarisation_primaire_province", "ips_tbs_primaire_region"],
}


def sans_accent(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texte).lower()) if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=1)
def dictionnaire() -> pd.DataFrame:
    d = pd.read_csv(DICTIONNAIRE, sep=";", encoding="utf-8-sig")
    return d.set_index("variable")


@lru_cache(maxsize=1)
def metadonnees() -> pd.DataFrame:
    """Libellé explicite et unité de chaque variable (dictionnaire des bases du modèle)."""
    m = pd.read_csv(METADONNEES, sep=";", encoding="utf-8-sig")
    m["priorite"] = (m["table"] != "panel_province_annee").astype(int)
    return m.sort_values("priorite").drop_duplicates("variable").set_index("variable")


def unite(v: str) -> str:
    m = metadonnees()
    return str(m.loc[v, "unite"]) if v in m.index and pd.notna(m.loc[v, "unite"]) else ""


@lru_cache(maxsize=1)
def valeurs() -> pd.DataFrame:
    """Valeur la plus récente de chaque indicateur pour chaque province (dernière valeur connue)."""
    b = D.base.sort_values(["province_pcode", "annee_scolaire"])
    variables = [c for c in b.columns if c not in NON_INDICATEURS and pd.api.types.is_numeric_dtype(b[c])]
    return b.groupby("province_pcode")[variables].agg(lambda s: s.dropna().iloc[-1] if s.notna().any() else np.nan)


def libelle(v: str) -> str:
    m = metadonnees()
    if v in m.index and pd.notna(m.loc[v, "libelle"]):
        texte = re.sub(r"\s*\((primaire|la province, 2019)\)", "", str(m.loc[v, "libelle"]))
        return texte[0].lower() + texte[1:] if texte[:2] != texte[:2].upper() else texte
    return nom_variable(v)


def description(v: str) -> str:
    d = dictionnaire()
    return str(d.loc[v, "description"]) if v in d.index else libelle(v)


def source(v: str) -> str:
    d = dictionnaire()
    return str(d.loc[v, "source"]) if v in d.index else "Base apurée du défi 1"


def formater(v: str, x) -> str:
    if x is None or pd.isna(x):
        return "n.d."
    x, u = float(x), unite(v)
    if u == "proportion":
        return f"{fr(100 * x)} %"
    if u in ("%", "points de %"):
        return f"{fr(x)} %" if u == "%" else f"{fr(x)} points"
    if u in ("indice", "rapport", "ratio"):
        return fr(x, 2)
    nombre = fr(x, 2 if abs(x) < 10 else (0 if abs(x) >= 1000 else 1))
    return f"{nombre} {u}".strip() if u and u not in ("sans unité",) else nombre


@lru_cache(maxsize=4)
def _taux(population: str) -> pd.Series:
    return D.tableau(population).set_index("province_pcode")["taux_abandon_prevu"]


def lien_avec_risque(v: str, population: str = "ensemble") -> float | None:
    x = valeurs()[v]
    y = _taux(population).reindex(x.index)
    ok = x.notna() & y.notna()
    if ok.sum() < 10 or x[ok].nunique() < 3:
        return None
    return round(float(spearmanr(x[ok], y[ok]).statistic), 2)


def lecture_lien(r: float | None) -> str:
    if r is None:
        return "lien non mesurable"
    force = "fort" if abs(r) >= 0.5 else ("modéré" if abs(r) >= 0.3 else "faible")
    sens = "plus il est élevé, plus le taux prévu est élevé" if r > 0 else "plus il est élevé, plus le taux prévu est bas"
    return f"lien {force} (corrélation de rang {fr(r, 2)}) : {sens}" if abs(r) >= 0.3 else f"lien faible (corrélation de rang {fr(r, 2)})"


def catalogue() -> list[dict]:
    return [{"variable": v, "libelle": libelle(v), "description": description(v)} for v in valeurs().columns]


def variables_de_la_question(question: str) -> list[str]:
    q = sans_accent(question)
    trouvees = []
    for mot, variables in MOTS_CLES.items():
        # Le mot doit commencer un mot de la question (« eau » ne doit pas répondre à « niveau »).
        if re.search(rf"(?<![a-z]){re.escape(mot)}", q):
            trouvees += [v for v in variables if v in valeurs().columns and v not in trouvees]
    return trouvees


def indicateurs_province(pcode: str, variables: list[str] | None = None, population: str = "ensemble") -> dict:
    """Valeurs d'une province pour une liste d'indicateurs (par défaut tous), avec médiane, rang et lien au risque."""
    t = valeurs()
    if pcode not in t.index:
        return {"erreur": f"Province inconnue : {pcode}"}
    variables = [v for v in (variables or list(t.columns)) if v in t.columns]
    facteurs = set(D.modeles[D.jeu(population)]["explication_lightgbm"]["variables"])
    nom = D.tableau_ensemble.set_index("province_pcode").loc[pcode, "province_nom"]
    lignes = []
    for v in variables:
        x = t[v]
        rang = int(x.rank(ascending=False, method="min")[pcode]) if pd.notna(x[pcode]) else None
        lignes.append({"indicateur": libelle(v), "variable": v, "description": description(v),
                       "valeur": formater(v, x[pcode]), "mediane_provinces": formater(v, x.median()),
                       "rang_sur_47_du_plus_eleve": rang, "lien_avec_le_risque": lecture_lien(lien_avec_risque(v, population)),
                       "facteur_du_modele": v in facteurs, "source": source(v)})
    return {"province": nom, "pcode": pcode, "indicateurs": lignes,
            "sources": sorted({l["source"] for l in lignes})[:6]}


def croissant(question: str) -> bool:
    """La question cherche les valeurs les plus basses (« où manque-t-il… », « le moins… »)."""
    q = sans_accent(question)
    return any(m in q for m in MOTS_CROISSANT)


def classement_indicateur(variable: str, region: str | None = None, population: str = "ensemble", n: int = 8,
                          plus_bas: bool = False) -> dict:
    """Provinces classées selon un indicateur (pays ou région), avec leur taux prévu et le lien avec le risque."""
    t = valeurs()
    if variable not in t.columns:
        return {"erreur": f"Indicateur inconnu : {variable}"}
    tb = D.tableau(population).set_index("province_pcode")
    x = t[variable].dropna()
    if region:
        x = x[[p for p in x.index if sans_accent(tb.loc[p, "region_nom"]) == sans_accent(region)]]
    x = x.sort_values(ascending=plus_bas)
    lignes = [{"province": tb.loc[p, "province_nom"], "pcode": p, "region": tb.loc[p, "region_nom"],
               "valeur": formater(variable, v), "taux_prevu_2025_2026": f"{fr(tb.loc[p, 'taux_abandon_prevu'])} %"}
              for p, v in x.head(n).items()]
    moyenne_region = formater(variable, x.mean()) if region and len(x) else None
    return {"indicateur": libelle(variable), "description": description(variable), "region": region,
            "mediane_nationale": formater(variable, t[variable].median()), "moyenne_de_la_region": moyenne_region,
            "ordre": "valeurs les plus basses d'abord" if plus_bas else "valeurs les plus élevées d'abord",
            "provinces": lignes,
            "lien_avec_le_risque": lecture_lien(lien_avec_risque(variable, population)),
            "sources": [source(variable)]}
