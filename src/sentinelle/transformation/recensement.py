"""Indicateurs du recensement de 2019 (RGPH 2019, volume 3 : pauvreté) à chaque niveau des panels.

La Sentinelle lit elle-même les 33 indicateurs de l'annexe du volume 3 (table fait_conditions_vie,
étape 02) pour les communes, les anciennes provinces, les anciennes régions et le pays. Ce module
les range dans les panels :

- anciennes provinces et anciennes régions : valeurs publiées ;
- provinces et régions de 2025 : valeur publiée quand l'unité réunit exactement les communes d'une
  ancienne unité ; sinon, moyenne des communes pondérée par leur population de 2019 (taux), ou somme
  des communes (population, ménages, pauvres) ;
- communes : valeurs publiées.

Les indicateurs sont mesurés une fois, en 2019, et répétés chaque année : ils expliquent les écarts
entre territoires, pas les évolutions d'une année à l'autre.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .panel import lire

SOURCE = "INSD, RGPH 2019, volume 3 (pauvreté), annexes"

# Variable lue -> (nom de base, libellé, unité). Le nom de base reçoit le suffixe du niveau.
INDICATEURS = {
    "incidence_pauvrete": ("pauvrete", "Incidence de la pauvreté", "%"),
    "profondeur_pauvrete": ("profondeur_pauvrete", "Profondeur de la pauvreté", "%"),
    "emploi_7_14": ("travail_enfants_7_14", "Enfants de 7 à 14 ans qui travaillent", "%"),
    "emploi_15_24": ("emploi_15_24", "Jeunes de 15 à 24 ans en emploi", "%"),
    "emploi_25_64": ("emploi_25_64", "Adultes de 25 à 64 ans en emploi", "%"),
    "chomage_15_24": ("chomage_15_24", "Chômage des 15-24 ans", "%"),
    "chomage_25_64": ("chomage_25_64", "Chômage des 25-64 ans", "%"),
    "travailleurs_autonomes_15_24": ("travailleurs_autonomes_15_24", "Travailleurs autonomes parmi les 15-24 ans en emploi", "%"),
    "travailleurs_autonomes_25_64": ("travailleurs_autonomes_25_64", "Travailleurs autonomes parmi les 25-64 ans en emploi", "%"),
    "frequentation_postprimaire": ("frequentation_post_primaire", "Fréquentation du post-primaire (enfants d'âge officiel scolarisés)", "%"),
    "frequentation_lycee": ("frequentation_secondaire", "Fréquentation du lycée (jeunes d'âge officiel scolarisés au secondaire)", "%"),
    "ratio_filles_garcons_primaire": ("parite_scolarisation_primaire", "Rapport filles / garçons de la scolarisation au primaire", "rapport"),
    "ratio_filles_garcons_post_primaire": ("parite_scolarisation_post_primaire", "Rapport filles / garçons de la scolarisation au post-primaire", "rapport"),
    "ratio_filles_garcons_secondaire": ("parite_scolarisation_secondaire", "Rapport filles / garçons de la scolarisation au secondaire", "rapport"),
    "hors_ecole_6_11": ("hors_ecole_6_11", "Enfants de 6 à 11 ans hors de l'école", "%"),
    "hors_ecole_12_15": ("hors_ecole_12_15", "Enfants de 12 à 15 ans hors de l'école", "%"),
    "hors_ecole_16_18": ("hors_ecole_16_18", "Jeunes de 16 à 18 ans hors de l'école", "%"),
    "ni_ecole_ni_travail_15_24": ("ni_ecole_ni_emploi_15_24", "Jeunes de 15 à 24 ans ni à l'école ni en emploi", "%"),
    "alphabetisation_15_64": ("alphabetisation_adultes", "Alphabétisation des 15-64 ans", "%"),
    "dependance_demographique": ("dependance_demographique", "Rapport de dépendance démographique au recensement", "%"),
    "filles_17_ans_mariees": ("filles_17_ans_mariees", "Filles de 17 ans mariées", "%"),
    "acte_naissance": ("acte_naissance", "Enfants ayant un acte de naissance", "%"),
    "sanitaires_ameliores": ("sanitaires_ameliores", "Ménages disposant de sanitaires améliorés", "%"),
    "eau_amelioree": ("eau_amelioree", "Ménages ayant accès à une eau améliorée", "%"),
    "electricite": ("electricite", "Ménages ayant l'électricité", "%"),
    "energie_cuisson_amelioree": ("cuisson_amelioree", "Ménages utilisant une énergie de cuisson améliorée", "%"),
    "telephone": ("telephone", "Ménages accédant à un téléphone", "%"),
}
COMPTES = {
    "population": ("population_rgph", "Population recensée en 2019", "personnes"),
    "menages": ("menages_rgph", "Ménages recensés en 2019", "ménages"),
    "nombre_pauvres": ("nombre_pauvres", "Personnes pauvres en 2019", "personnes"),
}
TOUS = {**INDICATEURS, **COMPTES}


def nom(source: str, niveau: str) -> str:
    """Nom de colonne : « _province » dans les panels provinciaux, « _region_2019 », « _commune_2019 » ailleurs."""
    base = TOUS[source][0]
    return f"{base}_province" if niveau == "province" else f"{base}_{niveau}_2019"


def colonnes(niveau: str) -> dict[str, str]:
    return {source: nom(source, niveau) for source in TOUS}


def _publie(niveau_geo: str | tuple, cle: str, niveau: str) -> pd.DataFrame:
    vie = lire("fait_conditions_vie")
    vie = vie[vie["niveau_geo"].isin([niveau_geo] if isinstance(niveau_geo, str) else niveau_geo)][["entite_pcode", *TOUS]]
    return vie.rename(columns={"entite_pcode": cle, **colonnes(niveau)})


def province_ancienne() -> pd.DataFrame:
    return _publie("province_ancienne", "province_ancienne_pcode", "province")


def region_ancienne() -> pd.DataFrame:
    """Anciennes régions et pays (code BF)."""
    return _publie(("region_ancienne", "pays"), "region_ancienne_pcode", "region")


def commune() -> pd.DataFrame:
    return _publie("commune", "commune_pcode", "commune")


def agreger_communes(communes: pd.DataFrame, cle: str, niveau: str) -> pd.DataFrame:
    """Unités définies par leurs communes (colonne cle du référentiel) : moyennes pondérées et sommes."""
    vie = lire("fait_conditions_vie")
    vie = vie[vie["niveau_geo"] == "commune"].merge(communes[["commune_pcode", cle]], left_on="entite_pcode",
                                                     right_on="commune_pcode")
    lignes = []
    for code, groupe in vie.groupby(cle):
        ligne = {cle: code}
        for source in INDICATEURS:
            valide = groupe[source].notna() & groupe["population"].notna()
            poids = groupe.loc[valide, "population"]
            ligne[nom(source, niveau)] = (float((groupe.loc[valide, source] * poids).sum() / poids.sum())
                                          if valide.any() else np.nan)
        for source in COMPTES:
            ligne[nom(source, niveau)] = groupe[source].sum(min_count=1)
        lignes.append(ligne)
    return pd.DataFrame(lignes)


def _identiques(communes: pd.DataFrame, nouvelle: str, ancienne: str) -> dict[str, str]:
    """Unités de 2025 qui réunissent exactement les communes d'une ancienne unité : code de 2025 -> ancien code."""
    paires = communes[[nouvelle, ancienne]].drop_duplicates()
    une_origine = paires.groupby(nouvelle)[ancienne].nunique() == 1
    un_heritier = paires.groupby(ancienne)[nouvelle].nunique() == 1
    return {n: a for n, a in zip(paires[nouvelle], paires[ancienne]) if une_origine[n] and un_heritier[a]}


def region_2025(communes: pd.DataFrame) -> pd.DataFrame:
    """Régions de 2025 : valeur publiée de l'ancienne région si elle est inchangée, sinon agrégat des communes."""
    table = agreger_communes(communes, "region_pcode", "region").set_index("region_pcode")
    publie = region_ancienne().set_index("region_ancienne_pcode")
    for nouvelle, ancienne in _identiques(communes, "region_pcode", "region_ancienne_pcode").items():
        table.loc[nouvelle, publie.columns] = publie.loc[ancienne]
    if "BF" in publie.index:
        table.loc["BF", publie.columns] = publie.loc["BF"]
    return table.reset_index()


def ajouter(table: pd.DataFrame, valeurs: pd.DataFrame, cle: str) -> pd.DataFrame:
    """Joint les indicateurs, en remplaçant les colonnes de même nom déjà présentes."""
    communes_cols = [c for c in valeurs.columns if c != cle]
    return table.drop(columns=[c for c in communes_cols if c in table]).merge(valeurs, on=cle, how="left")


def descriptions(niveau: str) -> dict[str, tuple[str, str, str, str]]:
    """Nom de colonne -> (libellé, unité, description, limites)."""
    echelle = {"province": "la province", "region": "la région", "commune": "la commune"}[niveau]
    sortie = {}
    for source, (_, libelle, unite) in TOUS.items():
        calcul = (f"valeur publiée pour {echelle} en 2019, répétée chaque année ; unités de 2025 issues d'une "
                  f"scission : moyenne des communes pondérée par la population de 2019" if source in INDICATEURS
                  else f"valeur publiée pour {echelle} en 2019 ; unités de 2025 issues d'une scission : somme des communes")
        if niveau == "commune":
            calcul = "valeur publiée pour la commune en 2019, répétée chaque année"
        limites = ("Mesure unique de 2019 : explique les écarts entre territoires, pas les évolutions ; ne voit pas "
                   "la crise après 2019")
        sortie[nom(source, niveau)] = (f"{libelle} ({echelle}, 2019)", unite, calcul, limites)
    return sortie


def controle(panel: pd.DataFrame, province_2025: pd.DataFrame, communes_panel: pd.DataFrame) -> tuple[bool, str]:
    """Population de 2019 : 45 anciennes provinces = 47 provinces de 2025 = 351 communes."""
    col = nom("population", "province")
    a = panel.drop_duplicates("province_ancienne_pcode")[col].sum()
    b = province_2025.drop_duplicates("province_pcode")[col].sum()
    c = communes_panel.drop_duplicates("commune_pcode")[nom("population", "commune")].sum()
    renseignes = sum(panel[nom(s, "province")].notna().all() for s in TOUS)
    conforme = abs(a - b) <= 1 and abs(a - c) / a < 0.01 and renseignes == len(TOUS)
    return bool(conforme), (f"{len(TOUS)} indicateurs du RGPH 2019 ({renseignes} complets pour les 45 provinces) ; "
                            f"population 2019 : 45 provinces {a:,.0f}, 47 provinces de 2025 {b:,.0f}, "
                            f"351 communes {c:,.0f}").replace(",", " ")
