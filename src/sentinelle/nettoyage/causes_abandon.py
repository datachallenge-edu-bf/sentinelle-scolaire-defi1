"""Causes déclarées de l'abandon (orpaillage, mariage, grossesse) et contexte minier, par région.

Tableaux de bord de l'enseignement primaire (DGESS), sections « Grossesses, violences et
causes » ou « Abandons liés à l'orpaillage, aux grossesses et aux mariages » : nombre
d'abandons par région selon la cause déclarée. Les données portent sur l'année scolaire
précédant l'édition (« Cas d'abandons … en 2022/2023 » dans l'édition 2023-2024) : l'année
est lue dans le texte de la page, à défaut déduite de l'édition. Le nom de région peut
être coupé sur deux lignes (« BOUCLE DU » puis « MOUHOUN 131 34 11 176 »).

Tableaux de bord du post-primaire et du secondaire : part de chaque cause et nombre de
cas par région ; les nombres par cause en sont déduits.

Annuaires régionaux de l'INSD : permis d'exploitation et sites miniers par typologie
(industrielle, semi-mécanisée, artisanale) et par année. Série lacunaire (absente pour
le Nord, le Centre-Nord, le Sahel et le Plateau Central, années variables), conservée
pour mémoire.
"""

from __future__ import annotations

import re

import pandas as pd

from .dgess import Identification, _trier
from .outils import Journal, cellules, colonnes_cellules, en_nombre, est_nombre, lire_extrait, normaliser_nom

TABLE = "fait_causes_abandon"
_NATIONAL = {"TOTAL", "BURKINAFASO", "ENSEMBLE"}
_ANNEE = re.compile(r"\b(?:en|En|EN)\s+(20\d\d)\s*/\s*(20\d\d)")


def _annee_des_donnees(textes: list[str], fichier: str) -> str:
    for texte in textes:
        if m := _ANNEE.search(texte):
            debut, fin = int(m.group(1)), int(m.group(2))
            if fin == debut + 1:
                return f"{debut}-{fin}"
    m = re.search(r"(20\d\d)_(20\d\d)", fichier) or re.search(r"_(20\d\d)\.pdf", fichier)
    fin = int(m.group(2) if m.lastindex == 2 else m.group(1))
    return f"{fin - 2}-{fin - 1}"


def _entite(nom: str, identifier: Identification) -> tuple[str, str] | None:
    if normaliser_nom(nom) in _NATIONAL:
        return ("BF", "pays")
    trouve = identifier(nom)
    return trouve if trouve and trouve[1] in ("region_ancienne", "pays") else None


def lire_causes(identifier: Identification, journal: Journal) -> pd.DataFrame:
    lignes = []
    brut = pd.concat([lire_extrait("dgess_tableaux_de_bord_primaire"),
                      lire_extrait("dgess_tableaux_de_bord_post_primaire")], ignore_index=True).fillna("")
    brut = _trier(brut.drop_duplicates(["source_fichier", "page", "ligne"]))
    colonnes = colonnes_cellules(brut)
    brut["_texte"] = brut[colonnes].apply(lambda r: " ".join(v.strip() for v in r if v.strip()), axis=1)
    for fichier, document in brut.groupby("source_fichier", sort=False):
        ordre = "post_primaire" if re.search(r"(?i)post", fichier) else "primaire"
        pages = dict(tuple(document.groupby("_page", sort=True)))
        for page, contenu in pages.items():
            texte_page = " ".join(contenu["_texte"])
            if ordre == "primaire" and not re.search(r"(?i)abandons? par r.gion selon les", texte_page):
                continue
            if ordre == "post_primaire" and not re.search(r"(?i)causes d.abandons? scolaires par r.gion", texte_page):
                continue
            # Année des données : dans la page du tableau ou dans la page de commentaire qui la précède.
            voisines = [pages[q] for q in (page - 1, page) if q in pages]
            textes = [t for c in voisines for t in c["_texte"] if re.search(r"(?i)abandon|cas d", t)]
            annee = _annee_des_donnees(textes, fichier)
            debut_tableau, attente = False, ""
            for _, row in contenu.iterrows():
                cel = cellules(row, colonnes)
                texte = " ".join(cel)
                if re.search(r"(?i)par r.gion selon les|causes d.abandons? scolaires par r.gion", texte):
                    debut_tableau = True
                    continue
                if not debut_tableau:
                    continue
                if re.search(r"(?i)grossesses par r.gion|^sources?\s*:", texte):
                    break
                # Lignes de pourcentages du graphique voisin, intercalées dans le tableau : ignorées.
                if not cel or all(re.fullmatch(r"[\d,.\s]+%", c) for c in cel):
                    continue
                if not est_nombre(cel[0]) and sum(1 for c in cel[1:] if est_nombre(c)) < 3 and not re.search(r"(?i)total|burkina", cel[0]):
                    attente = cel[0]          # nom de région coupé sur deux lignes
                    continue
                nom = f"{attente} {cel[0]}".strip() if attente else cel[0]
                trouve = _entite(nom, identifier) or (_entite(cel[0], identifier) if attente else None)
                attente = ""
                if trouve is None:
                    continue
                valeurs = [c for c in cel[1:] if est_nombre(c.rstrip("%").strip())]
                if ordre == "primaire" and len(valeurs) >= 3:
                    orpaillage, mariage, grossesse = (en_nombre(v) for v in valeurs[:3])
                elif ordre == "post_primaire" and len(valeurs) >= 4:
                    total = en_nombre(valeurs[3])
                    orpaillage, mariage, grossesse = (round(total * en_nombre(v.rstrip("%").strip()) / 100)
                                                      for v in valeurs[:3])
                else:
                    journal.noter(TABLE, "ligne écartée", "nombre de valeurs insuffisant", source=fichier, page=str(page),
                                  avant=" | ".join(cel)[:150])
                    continue
                lignes.append({"annee_scolaire": annee, "ordre": ordre, "entite_pcode": trouve[0],
                               "niveau_geo": "pays" if trouve[0] == "BF" else "region_ancienne",
                               "abandons_orpaillage": orpaillage, "abandons_mariage": mariage,
                               "abandons_grossesse": grossesse, "source_fichier": fichier, "page": page})
    table = pd.DataFrame(lignes)
    table["abandons_trois_causes"] = table[["abandons_orpaillage", "abandons_mariage", "abandons_grossesse"]].sum(axis=1)
    cles = ["annee_scolaire", "ordre", "entite_pcode"]
    doublons = table.duplicated(cles, keep="first")
    for r in table[doublons].itertuples():
        journal.noter(TABLE, "ligne écartée", "année déjà lue dans une autre édition", source=r.source_fichier,
                      page=str(r.page), avant=f"{r.annee_scolaire} {r.ordre} {r.entite_pcode}")
    return table[~doublons].sort_values(cles).reset_index(drop=True)


def lire_mines(identifier: Identification, journal: Journal) -> pd.DataFrame:
    """Permis et sites miniers par typologie, région et année (annuaires régionaux INSD)."""
    brut = _trier(lire_extrait("insd_mines_region"))
    colonnes = colonnes_cellules(brut)
    typologies = {"INDUSTRIELLE": "industrielle", "SEMIMECANISEE": "semi_mecanisee", "ARTISANALE": "artisanale",
                  "ENSEMBLE": "ensemble", "TOTAL": "ensemble"}
    lignes = []
    for fichier, document in brut.groupby("source_fichier", sort=False):
        nom_region = re.sub(r"(?i)^(INSD_)?annuaire_statistique_2024_|_?\d*\.pdf$", "", fichier).replace("_", " ")
        nom_region = re.sub(r"(?i)^(de la |du |des |de l |de )?r[ée]gion ", "", nom_region.strip())
        nom_region = re.sub(r"(?i)^(de la |du |des |de l |de |l )", "", nom_region.strip())
        region = identifier(nom_region)
        region = region[0] if region and region[1] == "region_ancienne" else None
        if region is None:
            journal.noter("fait_mines_region", "signalement", "région du fichier non reconnue", source=fichier)
            continue
        indicateur, annees, attente = None, [], ""
        for _, row in document.iterrows():
            cel = cellules(row, colonnes)
            texte = " ".join(cel)
            if re.search(r"(?i)tableau", texte):
                indicateur = ("permis" if re.search(r"(?i)permis d.exploitation", texte) else
                              "sites" if re.search(r"(?i)sites? miniers?", texte) else None)
                annees, attente = [], ""
                continue
            if indicateur is None or not cel:
                continue
            ans = [re.match(r"^(20\d\d)", c) for c in cel]
            if all(ans) and len(cel) >= 3:
                annees = [int(a.group(1)) for a in ans]
                continue
            if not est_nombre(cel[0]) and len(cel) == 1:
                attente = cel[0]
                continue
            cle = normaliser_nom(f"{attente}{cel[0]}") if attente else normaliser_nom(cel[0])
            attente = ""
            typologie = typologies.get(cle)
            if typologie is None or not annees:
                continue
            valeurs = cel[1:]
            if len(valeurs) != len(annees):
                continue
            for annee, valeur in zip(annees, valeurs):
                lignes.append({"annee": annee, "entite_pcode": region, "indicateur": indicateur, "typologie": typologie,
                               "valeur": en_nombre(valeur) if est_nombre(valeur) else None,
                               "source_fichier": fichier, "page": row["page"]})
    table = pd.DataFrame(lignes)
    return table.drop_duplicates(["annee", "entite_pcode", "indicateur", "typologie"]).sort_values(
        ["entite_pcode", "indicateur", "typologie", "annee"]).reset_index(drop=True)


def controler(causes: pd.DataFrame, mines: pd.DataFrame) -> dict[str, tuple[bool, str]]:
    prim = causes[causes["ordre"] == "primaire"]
    regions = prim[prim["niveau_geo"] == "region_ancienne"].groupby("annee_scolaire")["entite_pcode"].nunique()
    somme = prim[prim["niveau_geo"] == "region_ancienne"].groupby("annee_scolaire")["abandons_trois_causes"].sum()
    national = prim[prim["niveau_geo"] == "pays"].set_index("annee_scolaire")["abandons_trois_causes"]
    commun = somme.index.intersection(national.index)
    ecart = (somme.loc[commun] - national.loc[commun]).abs()
    return {
        "causes_abandon_13_regions": (bool((regions == 13).all()),
                                      "; ".join(f"{a} : {v}" for a, v in regions.items())),
        "causes_abandon_regions_egal_national": (bool((ecart <= 1).all()) and len(ecart) > 0,
                                                 f"somme des régions = total national pour {int((ecart <= 1).sum())} "
                                                 f"années sur {len(ecart)}"),
        "mines_couverture": (True, f"{mines['entite_pcode'].nunique()} régions sur 13, années "
                                   f"{int(mines['annee'].min())} à {int(mines['annee'].max())} selon les régions ; "
                                   "conservé pour mémoire, hors du modèle"),
    }
