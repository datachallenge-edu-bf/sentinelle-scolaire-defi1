"""Post-primaire et secondaire : indicateurs par province et conditions d'accueil par région.

Source : annuaires statistiques de la DGESS sur le post-primaire et le secondaire, de
2018-2019 à 2022-2023 (2019-2020 dans le Data Pack, les autres fournis par l'équipe).

Pour la Sentinelle, ce qui se passe après le CM2 éclaire le décrochage du primaire : une
province où peu d'élèves entrent en 6e, ou d'où ils partent vite, offre peu de
perspective, et les familles retiennent moins leurs enfants à l'école.

Une page est reconnue d'après les mots de son titre et de ses en-têtes de colonnes :

- indicateurs par province (une ligne par province : population de référence, effectif,
  taux pour garçons, filles et ensemble, puis l'indice de parité) : TBA en 6e et en 2nde,
  TBS et taux nets du post-primaire (12-15 ans), du secondaire (16-18 ans) et de
  l'ensemble (12-18 ans), taux d'achèvement en 3e et en terminale ;
- taux de flux par province et classe (promotion, redoublement, abandon, de la 6e à la
  terminale ; la 3e et la terminale n'ont que le redoublement) ;
- conditions d'accueil par région, sous-tableau du public : commodités des
  établissements, état des salles, ratio élèves par classe.

Les noms de région sont parfois tronqués (« BOUCLE DU MOUH ») : ils sont reconnus par leur
début. Deux tables longues : ``fait_secondaire_province`` et ``fait_secondaire_region``.
"""

from __future__ import annotations

import re

import pandas as pd

from .conditions_scolarisation import _sans_accent
from .dgess import Identification, _trier
from .outils import Journal, cellules, colonnes_cellules, en_nombre, lire_extrait, normaliser_nom

JEU = "dgess_annuaires_post_primaire"
TABLE_PROVINCE = "fait_secondaire_province"
TABLE_REGION = "fait_secondaire_region"
SEXES = ["G", "F", "T"]
MESURES = ["population", "effectif", "taux"]
CLASSES = [("6e", 3), ("5e", 3), ("4e", 3), ("3e", 1), ("2nde", 3), ("1ere", 3), ("tle", 1)]
COMMODITES = ["eau_potable", "electricite", "latrines", "cantine", "internat", "bibliotheque", "infirmerie",
              "terrain_sport", "salle_informatique", "laboratoire_pc", "laboratoire_svt", "magasin", "logements",
              "cloture", "etablissements"]
ETAT_SALLES = ["portes_bois", "portes_metal", "sans_porte", "portes_bon", "portes_mauvais", "toit_bon",
               "toit_mauvais", "murs_bon", "murs_mauvais", "electricite_bon", "electricite_mauvais",
               "sans_electricite", "salles"]
RATIOS = ["ratio_6e", "ratio_5e", "ratio_4e", "ratio_3e", "ratio_post_primaire", "ratio_2nde", "ratio_1ere",
          "ratio_tle", "ratio_secondaire"]


def _type_de_page(tete: str) -> tuple[str, str] | None:
    """(famille, indicateur ou sous-tableau) d'après le titre et les en-têtes de colonnes."""
    t = re.sub(r"\s+", " ", tete)
    if "...." in t:
        return None
    if "TAUX DE FLUX" in t:
        for mot, sexe in [("GARCONS+FILLES", "T"), ("GARCONS + FILLES", "T"), ("GARCONS", "G"), ("FILLES", "F")]:
            if mot in t:
                return ("flux", sexe)
        return None
    if "NOUVEAUX INSCRITS EN 6" in t:
        return ("indicateur", "tba_6e")
    if "NOUVEAUX INSCRITS EN 2" in t:
        return ("indicateur", "tba_2nde")
    if "ACHEVEMENT" in t and ("3EME" in t or "3IEME" in t or "TROISIEME" in t):
        return ("indicateur", "tach_post_primaire")
    if "ACHEVEMENT" in t and re.search(r"TERMINALE|\bTLE\b", t):
        return ("indicateur", "tach_secondaire")
    for mots, prefixe in [("BRUT DE SCOLARISATION", "tbs"), ("NET DE SCOLARISATION", "tns")]:
        if mots in t:
            for age, ordre in [("12-18", "ensemble"), ("12-15", "post_primaire"), ("16-18", "secondaire")]:
                if re.search(age.replace("-", r"\s*[-‐]\s*"), t):
                    return ("indicateur", f"{prefixe}_{ordre}")
    # Conditions d'accueil : enseignement général seulement (section III ; la section IV, technique,
    # reprend les mêmes titres).
    if re.search(r"(?<![IV])III\s*\.\s*\d", t) and re.search(r"PUBLIC(?!\s*\+)", t) and not re.search(r"PUBLIC\s*\+\s*PRIVE", t):
        if "COMMODITE" in t:
            return ("region", "commodites")
        if "ETAT DES SALLES" in t:
            return ("region", "etat_salles")
        if "RATIO ELEVES/CLASSE" in t.replace(" / ", "/") or "RATIO ELEVE/CLASSE" in t:
            return ("region", "ratio_eleves_classe")
    return None


class _Entites:
    """Province, région ou pays d'après un libellé ; région tronquée reconnue par son début."""

    def __init__(self, identifier: Identification, alias: pd.DataFrame):
        self.identifier = identifier
        regions = alias[alias["niveau"] == "region_ancienne"]
        self.regions = dict(zip(regions["nom_normalise"], regions["pcode"]))

    def __call__(self, libelle: str, region: str | None) -> tuple[str, str] | None:
        n = normaliser_nom(libelle)
        if n.startswith("TOTALREGION") or n == "TOTAL":
            return (region, "region_ancienne") if region else None
        if n.startswith(("TOTALNATIONAL", "BURKINA")):
            return ("BF", "pays")
        trouve = self.identifier(libelle)
        if trouve:
            return trouve
        debuts = {p for nom, p in self.regions.items() if len(n) >= 6 and nom.startswith(n)}
        return (debuts.pop(), "region_ancienne") if len(debuts) == 1 else None


def _valeur(texte: str) -> float:
    return en_nombre(texte.replace("%", "").strip())


def lire_post_primaire(identifier: Identification, alias: pd.DataFrame,
                       journal: Journal) -> tuple[pd.DataFrame, pd.DataFrame]:
    brut = _trier(lire_extrait(JEU))
    colonnes = colonnes_cellules(brut)
    entites = _Entites(identifier, alias)
    brut["_texte"] = brut[colonnes].apply(lambda r: " ".join(v.strip() for v in r if v and v.strip()), axis=1)
    province, region_lignes = [], []
    for fichier, document in brut.groupby("source_fichier", sort=False):
        region, precedent = None, None
        for page, contenu in document.groupby("_page", sort=True):
            tete = _sans_accent(" ".join(contenu["_texte"].head(8)))
            annee = re.search(r"ANNEE SCOLAIRE (20\d\d)\s*[-/]\s*(20\d\d)", tete)
            genre = _type_de_page(tete)
            if genre is None or annee is None:
                precedent = None
                continue
            annee = f"{annee.group(1)}-{annee.group(2)}"
            if genre != precedent:
                region = None  # nouveau tableau : la région de la page précédente ne vaut plus
            precedent = genre
            attente_pays = False
            for _, row in contenu.iterrows():
                cel = cellules(row, colonnes)
                if not cel:
                    continue
                n_texte = next((i for i, c in enumerate(cel) if pd.notna(_valeur(c))), len(cel))
                nom, valeurs = " ".join(cel[:n_texte]), [_valeur(c) for c in cel[n_texte:]]
                if normaliser_nom(nom).startswith("TOTALNATIONAL") and not valeurs:
                    attente_pays = True
                    continue
                if not valeurs:
                    trouve = entites(nom, region) if nom else None
                    if trouve and trouve[1] == "region_ancienne":
                        region = trouve[0]
                    continue
                if not nom and attente_pays:
                    entite = ("BF", "pays")
                else:
                    entite = entites(nom, region) if nom else None
                attente_pays = False
                if entite is None:
                    if len(valeurs) > 3:
                        journal.noter(TABLE_PROVINCE if genre[0] != "region" else TABLE_REGION, "ligne écartée",
                                      "entité non reconnue", source=fichier, page=str(page), avant=" ".join(cel))
                    continue
                if entite[1] == "region_ancienne":
                    region = entite[0]
                attendu = {"indicateur": 10, "flux": 17}.get(genre[0]) or len(
                    {"commodites": COMMODITES, "etat_salles": ETAT_SALLES, "ratio_eleves_classe": RATIOS}[genre[1]])
                # « #DIV/0! » (division par zéro du tableur source, province sans secondaire) : valeur absente,
                # la ligne reste lue pour les autres classes.
                absentes = [c.startswith("#DIV") for c in cel[n_texte:]]
                if len(valeurs) != attendu or any(pd.isna(v) and not a for v, a in zip(valeurs, absentes)):
                    motif = (f"{len(valeurs)} valeurs au lieu de {attendu}" if len(valeurs) != attendu
                             else "valeur non numérique dans la ligne")
                    journal.noter(TABLE_PROVINCE if genre[0] != "region" else TABLE_REGION, "ligne écartée",
                                  motif, source=fichier, page=str(page),
                                  avant=" ".join(cel))
                    continue
                commun = {"annee_scolaire": annee, "entite_pcode": entite[0], "niveau": entite[1],
                          "source_fichier": fichier, "page": str(page)}
                if genre[0] == "indicateur":
                    for i, mesure in enumerate(MESURES):
                        for j, sexe in enumerate(SEXES):
                            province.append({**commun, "indicateur": genre[1], "mesure": mesure, "sexe": sexe,
                                             "valeur": valeurs[3 * i + j]})
                    province.append({**commun, "indicateur": genre[1], "mesure": "indice_parite", "sexe": "T",
                                     "valeur": valeurs[9]})
                elif genre[0] == "flux":
                    position = 0
                    for classe, largeur in CLASSES:
                        noms = ["promotion", "redoublement", "abandon"] if largeur == 3 else ["redoublement"]
                        for k, mesure in enumerate(noms):
                            if pd.isna(valeurs[position + k]):
                                continue
                            province.append({**commun, "indicateur": f"flux_{classe}", "mesure": mesure,
                                             "sexe": genre[1], "valeur": valeurs[position + k]})
                        position += largeur
                else:
                    noms = {"commodites": COMMODITES, "etat_salles": ETAT_SALLES,
                            "ratio_eleves_classe": RATIOS}[genre[1]]
                    for nom_var, v in zip(noms, valeurs):
                        region_lignes.append({**commun, "tableau": genre[1], "statut": "public",
                                              "indicateur": nom_var, "valeur": v})
    cles_p = ["annee_scolaire", "entite_pcode", "indicateur", "mesure", "sexe"]
    cles_r = ["annee_scolaire", "entite_pcode", "tableau", "indicateur"]
    sortie = []
    for lignes, cles, nom in [(province, cles_p, TABLE_PROVINCE), (region_lignes, cles_r, TABLE_REGION)]:
        table = pd.DataFrame(lignes)
        doublons = table[table.duplicated(cles, keep=False)]
        conflits = doublons.groupby(cles)["valeur"].nunique()
        for cle in conflits[conflits > 1].index:
            journal.noter(nom, "doublon", "valeurs différentes pour une même clé : la première est gardée",
                          avant=" ".join(map(str, cle)))
        sortie.append(table.drop_duplicates(cles).sort_values(cles).reset_index(drop=True))
    return sortie[0], sortie[1]


def controler(province: pd.DataFrame, region: pd.DataFrame) -> dict[str, tuple[bool, str]]:
    ind = province[~province["indicateur"].str.startswith("flux_")]
    large = ind.pivot_table(index=["annee_scolaire", "entite_pcode", "indicateur", "sexe"], columns="mesure",
                            values="valeur").dropna(subset=["population", "effectif", "taux"])
    large = large[large["population"] > 0]
    ecart = (100 * large["effectif"] / large["population"] - large["taux"]).abs()
    couverture = ind[ind["niveau"] == "province_ancienne"].groupby(["annee_scolaire", "indicateur"])[
        "entite_pcode"].nunique()
    flux = province[province["indicateur"].str.startswith("flux_")].pivot_table(
        index=["annee_scolaire", "entite_pcode", "indicateur", "sexe"], columns="mesure", values="valeur")
    flux = flux.dropna(subset=["promotion", "abandon"])
    somme = flux[["promotion", "redoublement", "abandon"]].sum(axis=1)
    reg = region.pivot_table(index=["annee_scolaire", "entite_pcode", "tableau"], columns="indicateur",
                             values="valeur")
    commodites = reg.xs("commodites", level="tableau").dropna(axis=1, how="all")
    plafond = (commodites.drop(columns="etablissements").le(commodites["etablissements"], axis=0)).all(axis=1)
    annees = sorted(province["annee_scolaire"].unique())
    return {
        "post_primaire_cinq_annees": (len(annees) == 5, "années lues : " + ", ".join(annees)),
        "post_primaire_45_provinces": (bool((couverture >= 44).all()) and len(couverture) == 50,
                                       f"{len(couverture)} indicateurs × années, provinces : minimum "
                                       f"{couverture.min()}, maximum {couverture.max()}"),
        "post_primaire_taux_recalcule": (bool((ecart <= 0.15).mean() >= 0.98),
                                         f"taux = 100 × effectif / population à 0,15 point près pour "
                                         f"{int((ecart <= 0.15).sum())} lignes sur {len(ecart)}"),
        "post_primaire_flux_somme_100": (bool(((somme - 100).abs() <= 0.3).mean() >= 0.98),
                                         f"promotion + redoublement + abandon = 100 % à 0,3 point près pour "
                                         f"{int(((somme - 100).abs() <= 0.3).sum())} lignes sur {len(somme)}"),
        "post_primaire_commodites_sous_total": (bool(plafond.all()),
                                                f"aucune commodité ne dépasse le nombre d'établissements : "
                                                f"{int(plafond.sum())} régions × années sur {len(plafond)}"),
    }
