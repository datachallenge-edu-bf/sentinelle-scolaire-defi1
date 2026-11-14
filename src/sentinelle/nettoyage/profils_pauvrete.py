"""Profils régionaux de pauvreté (INSD, octobre 2023) : consommation et inégalités par province et commune.

Les dix profils régionaux publiés en 2023 reprennent la mesure de la pauvreté de
l'EHCVM 2018 et du RGPH 2019 : l'incidence et la profondeur y sont identiques à celles
du volume 3 du recensement (contrôle ``profils_incidence_egale_recensement``). Ils
ajoutent, pour l'année de référence 2019, la sévérité de la pauvreté (selon les
régions), la consommation par personne et les indicateurs d'inégalité (Gini, Theil,
rapports interdéciles), par province et par commune. Les profils de la Boucle du
Mouhoun, des Cascades et du Centre-Est ne figurent pas dans le Data Pack.

Quatre tableaux sont lus : pauvreté selon les provinces, pauvreté selon les communes,
inégalités par milieu et par province, inégalités par commune. Chaque tableau se
poursuit jusqu'au titre suivant ; les communes sont rattachées à la province de
l'intertitre « Province du … » qui les précède ; leur nom est cherché parmi les communes
de la région du fichier, où il est unique (l'intertitre n'est pas toujours répété d'une
page à l'autre). Les arrondissements de Ouagadougou et de Bobo-Dioulasso sont écartés :
la valeur de la commune entière n'est pas publiée dans ces tableaux.
"""

from __future__ import annotations

import re
from difflib import get_close_matches

import pandas as pd

from .dgess import Identification, _trier
from .outils import Journal, cellules, colonnes_cellules, en_nombre, est_nombre, lire_extrait, normaliser_nom

TABLE = "fait_profils_pauvrete"
TABLEAUX = [
    (r"PAUVRET\w* SELON LES PROVINCES", "pauvrete", "province_ancienne"),
    (r"INDICATEURS DE PAUVRET\w* SELON LES COMMUNES", "pauvrete", "commune"),
    (r"IN\w*GALIT\w* DE LA CONSOMMATION PAR MILIEU", "inegalites", "province_ancienne"),
    (r"IN\w*GALIT\w* DE LA CONSOMMATION PAR COMMUNE", "inegalites", "commune"),
]
COLONNES = {
    ("pauvrete", 5): ["incidence", "contribution", "profondeur", "severite", "consommation_par_personne"],
    ("pauvrete", 4): ["incidence", "contribution", "profondeur", "consommation_par_personne"],
    ("inegalites", 5): ["gini", "theil_0", "theil_1", "rapport_q90_q10", "rapport_q90_q50"],
}
# Orthographes trop éloignées de COD-AB pour le rapprochement automatique (ou nom coupé en fin de ligne).
ORTHOGRAPHES = {"GOURCY": "GOURSI", "BOUROUM": "BOUROUMBOUROUM"}
_IGNORES = {"ENSEMBLE", "ENSEMBLEREGION", "URBAIN", "RURAL", "TOTAL", "MILIEUDERESIDENCE", "PROVINCES", "COMMUNES"}


def _majuscules(texte: str) -> str:
    return re.sub(r"\s+", " ", texte.upper().translate(str.maketrans("ÉÈÊËÀÂÎÏÔÛÙÇ’", "EEEEAAIIOUUC'")))


def lire_profils(identifier: Identification, communes: pd.DataFrame, journal: Journal) -> pd.DataFrame:
    brut = _trier(lire_extrait("insd_profils_pauvrete"))
    colonnes = colonnes_cellules(brut)
    par_region = {r: dict(zip(g["commune_nom"].map(normaliser_nom), g["commune_pcode"]))
                  for r, g in communes.groupby("region_ancienne_pcode")}
    lignes = []
    for fichier, document in brut.groupby("source_fichier", sort=False):
        nom_region = re.sub(r"^PROFIL_DE_PAUVRETE_|_VF\.PDF$", "", fichier.upper()).replace("_", " ")
        region = identifier(nom_region)
        region = region[0] if region and region[1] == "region_ancienne" else None
        tableau, province = None, None
        for _, row in document.iterrows():
            cel = cellules(row, colonnes)
            if not cel:
                continue
            texte = _majuscules(" ".join(cel))
            if re.match(r"^(TABLEAU|GRAPHIQUE)\s*\d", texte):
                tableau = None if "...." in texte else next(
                    ((genre, niveau) for motif, genre, niveau in TABLEAUX if re.search(motif, texte)), None)
                province = None
                continue
            if tableau is None:
                continue
            if m := re.match(r"^PROVINCE (DU|DE LA|DE L'|DES|DE) ?(.+)$", texte):
                trouve = identifier(m.group(2))
                province = trouve[0] if trouve and trouve[1] == "province_ancienne" else None
                continue
            nombres = [c for c in cel[1:] if est_nombre(c)]
            if est_nombre(cel[0]) or len(nombres) != len(cel) - 1 or normaliser_nom(cel[0]) in _IGNORES:
                continue
            noms = COLONNES.get((tableau[0], len(nombres)))
            if noms is None:
                continue
            if tableau[1] == "province_ancienne":
                trouve = identifier(cel[0])
                if trouve is None or trouve[1] != "province_ancienne":
                    continue
                code = trouve[0]
            else:
                if re.match(r"^(OUAGA|BOBO) ?(ARR|RURAL)", _majuscules(cel[0])):
                    continue
                candidats = par_region.get(region, {})
                cle = normaliser_nom(cel[0])
                cle = next((v for k, v in ORTHOGRAPHES.items() if cle.startswith(k)), cle)
                proche = candidats.get(cle) or next((candidats[k] for k in get_close_matches(cle, list(candidats), 1, 0.7)), None)
                if proche is None:
                    journal.noter(TABLE, "signalement", "commune du profil sans correspondance COD-AB", source=fichier,
                                  page=str(row["page"]), avant=cel[0], apres=str(province))
                    continue
                code = proche
            for variable, valeur in zip(noms, nombres):
                lignes.append({"niveau_geo": tableau[1], "entite_pcode": code, "libelle": cel[0], "variable": variable,
                               "valeur": en_nombre(valeur), "source_fichier": fichier, "page": row["page"]})
    long = pd.DataFrame(lignes).drop_duplicates(["niveau_geo", "entite_pcode", "variable"], keep="first")
    large = long.pivot_table(index=["niveau_geo", "entite_pcode"], columns="variable", values="valeur").reset_index()
    origine = long.groupby(["niveau_geo", "entite_pcode"]).agg(libelle=("libelle", "first"),
                                                               source_fichier=("source_fichier", "first"),
                                                               page=("page", "min")).reset_index()
    large = origine.merge(large, on=["niveau_geo", "entite_pcode"])
    large.columns.name = None
    large["annee_reference"] = 2019
    ordre = ["niveau_geo", "entite_pcode", "libelle", "annee_reference", "incidence", "contribution", "profondeur",
             "severite", "consommation_par_personne", "gini", "theil_0", "theil_1", "rapport_q90_q10", "rapport_q90_q50",
             "source_fichier", "page"]
    for colonne in ordre:
        if colonne not in large:
            large[colonne] = float("nan")
    return large[ordre].sort_values(["niveau_geo", "entite_pcode"]).reset_index(drop=True)


def controler(profils: pd.DataFrame, vie: pd.DataFrame) -> dict[str, tuple[bool, str]]:
    n = profils.groupby("niveau_geo")["entite_pcode"].nunique()
    reference = vie.set_index(["niveau_geo", "entite_pcode"])["incidence_pauvrete"]
    commun = profils.set_index(["niveau_geo", "entite_pcode"])["incidence"].dropna()
    commun = commun[commun.index.isin(reference.index)]
    ecart = (commun - reference.loc[commun.index]).abs()
    return {
        "profils_couverture": (n.get("province_ancienne", 0) >= 30,
                               f"{n.get('province_ancienne', 0)} provinces et {n.get('commune', 0)} communes de 10 régions "
                               "(pas de profil pour la Boucle du Mouhoun, les Cascades et le Centre-Est)"),
        "profils_incidence_egale_recensement": (
            bool((ecart <= 0.15).mean() >= 0.95),
            f"incidence identique à celle du RGPH 2019 (vol. 3) pour {int((ecart <= 0.15).sum())} entités sur {len(ecart)} : "
            "les profils de 2023 reprennent la mesure de 2019"),
    }
