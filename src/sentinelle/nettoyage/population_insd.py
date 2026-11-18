"""Projections de population actualisées de l'INSD, par âge simple et sexe.

Classeurs téléchargés du portail OpenDataForAfrica de l'INSD (copie brute dans l'extrait
``insd_projections_actualisees``) :

- communes, 2020 à 2025 : un classeur par région de 2025, une feuille par province, un tableau
  par commune puis celui de la province ;
- provinces de 2025, 2020 à 2035 : un classeur par région, un tableau par province puis celui
  de la région ;
- pays, 2020 à 2035, et anciennes projections nationales 2007 à 2018.

Chaque feuille est lue comme une grille. Une ligne y joue un rôle : nom d'entité, années,
sexes (ordre lu dans l'en-tête, il varie selon les fichiers), âge (0 à 79, « 80+ ») ou total.
Les lignes de total ferment un tableau ; un tableau sans total (projections 2007-2018) se
ferme en fin de feuille. Dans un classeur provincial, le dernier tableau est celui de la région.
Les noms sont reconnus parmi les communes et provinces de 2025 (COD-AB) de la province ou de la
région du fichier. Le total publié de chaque tableau est gardé pour le contrôle.

Sortie : ``fait_population`` (année × niveau × entité × âge × sexe), codes de 2025.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

import pandas as pd

from .communes_insd import ORTHOGRAPHES as ORTHOGRAPHES_COMMUNES
from .outils import Journal, lire_extrait, normaliser_nom

TABLE = "fait_population"
SEXES = {"HOMME": "G", "HOMMES": "G", "FEMME": "F", "FEMMES": "F", "ENSEMBLE": "T"}
NOMS_CLASSEURS = {**ORTHOGRAPHES_COMMUNES, "KOOSIN": "KOSSIN", "LORUM": "LOROUM", "KOMONDJOARI": "KOMANDJARI",
                  "BOBO": "BOBODIOULASSO"}


def _valeur(texte: str) -> float | None:
    try:
        return float(str(texte).replace(" ", "").replace(" ", ""))
    except ValueError:
        return None


def _role(cellules: list[str]) -> tuple[str, object]:
    """Rôle d'une ligne de la grille et son contenu utile."""
    if not cellules:
        return "vide", None
    nombres = [_valeur(c) for c in cellules]
    if all(n is not None and 1990 < n < 2100 for n in nombres):
        return "annees", [int(n) for n in nombres]
    etiquettes = [SEXES.get(normaliser_nom(c)) for c in cellules]
    if sum(e is not None for e in etiquettes) >= 3:
        return "sexes", [e for e in etiquettes if e][:3]
    tete = normaliser_nom(cellules[0])
    if tete == "TOTAL":
        return "total", [n for n in nombres[1:] if n is not None]
    # « 80+ » seulement par son libellé : « 8.0 » (âge 8 écrit en décimal) se normaliserait aussi en « 80 ».
    if cellules[0].replace(" ", "") == "80+":
        return "age", (80, [n for n in nombres[1:] if n is not None])
    if nombres[0] is not None and nombres[0] == int(nombres[0]) and 0 <= nombres[0] < 80 and len(cellules) > 1:
        return "age", (int(nombres[0]), [n for n in nombres[1:] if n is not None])
    if tete.startswith(("COMMUNE", "PROVINCE", "REGION")) and len(cellules) >= 2:
        return "nom", (tete[:7].lower(), cellules[1])
    if len(cellules) == 1 and nombres[0] is None and not tete.startswith("AGE"):
        return "nom", ("seul", cellules[0])
    return "autre", None


def _tableaux(grille: pd.DataFrame, colonnes: list[str]) -> list[dict]:
    """Tableaux d'une feuille : nom, années, sexes, lignes d'âge, total publié."""
    tableaux, courant = [], {"nom": None, "annees": [], "sexes": [], "ages": []}
    for _, rang in grille.iterrows():
        role, contenu = _role([str(rang[c]).strip() for c in colonnes if str(rang[c]).strip()])
        if role == "nom":
            courant["nom"] = contenu
        elif role in ("annees", "sexes"):
            courant[role] = contenu
        elif role == "age":
            courant["ages"].append(contenu)
        elif role == "total":
            tableaux.append({**courant, "total": contenu})
            courant = {"nom": None, "annees": courant["annees"], "sexes": courant["sexes"], "ages": []}
    if courant["ages"]:
        tableaux.append({**courant, "total": []})
    return tableaux


class _Territoires:
    def __init__(self, communes: pd.DataFrame):
        self.communes = communes
        self.provinces = communes.drop_duplicates("province_pcode")
        self.regions = communes.drop_duplicates("region_pcode")

    @staticmethod
    def _chercher(nom: str, noms: pd.Series, codes: pd.Series) -> str | None:
        n = normaliser_nom(re.sub(r"(?i)^(commune|province|r[ée]gion)\s*:\s*", "", nom))
        n = NOMS_CLASSEURS.get(n, n)
        normalises = noms.map(normaliser_nom)
        egaux = codes[normalises == n]
        if len(egaux) == 1:
            return egaux.iloc[0]
        scores = normalises.map(lambda x: SequenceMatcher(None, n, x).ratio())
        return codes.loc[scores.idxmax()] if len(scores) and scores.max() >= 0.8 else None

    def region(self, fichier: str) -> str | None:
        nom = re.sub(r"(?i)\s*\(\d\)|\.xlsx$|par age revise ok", "", fichier).strip()
        return self._chercher(nom, self.regions["region_nom"], self.regions["region_pcode"])

    def province(self, nom: str, region: str | None = None) -> str | None:
        p = self.provinces if region is None else self.provinces[self.provinces["region_pcode"] == region]
        return self._chercher(nom, p["province_nom"], p["province_pcode"])

    def commune(self, nom: str, province: str) -> str | None:
        c = self.communes[self.communes["province_pcode"] == province]
        return self._chercher(nom, c["commune_nom"], c["commune_pcode"])


def lire_population(communes: pd.DataFrame, journal: Journal) -> tuple[pd.DataFrame, pd.DataFrame]:
    brut = lire_extrait("insd_projections_actualisees")
    brut = brut.assign(_ligne=pd.to_numeric(brut["ligne"])).sort_values(["source_fichier", "feuille", "_ligne"])
    colonnes = sorted((c for c in brut.columns if re.fullmatch(r"col\d+", c)), key=lambda c: int(c[3:]))
    territoires = _Territoires(communes)
    valeurs, totaux = [], []
    for fichier, classeur in brut.groupby("source_fichier", sort=False):
        communal = "PAR AGE" in fichier.upper()
        national = fichier.upper().startswith(("BURKINA", "PROJECTIONS"))
        region = None if national else territoires.region(fichier)
        for feuille, grille in classeur.groupby("feuille", sort=False):
            tableaux = _tableaux(grille, colonnes)
            for rang, t in enumerate(tableaux):
                genre, nom = t["nom"] if t["nom"] else ("seul", "")
                if normaliser_nom(nom) == "DIFFERENCE":
                    continue  # ligne de contrôle propre aux classeurs de l'INSD
                if national:
                    niveau, code = "pays", "BF"
                elif communal:
                    province = territoires.province(feuille, region)
                    niveau, code = (("commune", territoires.commune(nom, province)) if genre == "commune"
                                    else ("province", province))
                elif rang == len(tableaux) - 1 and len(tableaux) > 1:
                    niveau, code = "region", region
                else:
                    niveau, code = "province", territoires.province(nom, region)
                attendu = 3 * len(t["annees"])
                if code is None or len(t["sexes"]) != 3:
                    journal.noter(TABLE, "tableau écarté", "entité ou en-tête non reconnu", source=fichier,
                                  page=feuille, avant=nom)
                    continue
                for age, nombres in t["ages"]:
                    if len(nombres) != attendu:
                        journal.noter(TABLE, "ligne écartée", f"{len(nombres)} valeurs au lieu de {attendu}",
                                      source=fichier, page=feuille, ligne=str(age), avant=nom)
                        continue
                    for k, v in enumerate(nombres):
                        valeurs.append({"annee": t["annees"][k // 3], "niveau_geo": niveau, "entite_pcode": code,
                                        "age": age, "sexe": t["sexes"][k % 3], "population": v,
                                        "source_fichier": fichier})
                if len(t["total"]) == attendu:
                    totaux += [{"annee": t["annees"][k // 3], "niveau_geo": niveau, "entite_pcode": code,
                                "sexe": t["sexes"][k % 3], "total_publie": v, "source_fichier": fichier}
                               for k, v in enumerate(t["total"])]
    table = pd.DataFrame(valeurs)
    totaux = pd.DataFrame(totaux)
    # Une même province figure dans le classeur communal et dans le classeur provincial : une seule valeur gardée.
    cles = ["annee", "niveau_geo", "entite_pcode", "age", "sexe"]
    ecarts = table.groupby(cles)["population"].nunique()
    for cle in ecarts[ecarts > 1].index[:20]:
        journal.noter(TABLE, "doublon", "valeurs différentes entre deux classeurs : la première est gardée",
                      avant=" ".join(map(str, cle)))
    return table, totaux


def controler(table: pd.DataFrame, totaux: pd.DataFrame, communes: pd.DataFrame,
              vie: pd.DataFrame) -> dict[str, tuple[bool, str]]:
    cles = ["annee", "niveau_geo", "entite_pcode", "sexe", "source_fichier"]
    sommes = table.groupby(cles)["population"].sum()
    publies = totaux.set_index(cles)["total_publie"]
    commun = sommes.index.intersection(publies.index)
    e1 = (sommes.loc[commun] - publies.loc[commun]).abs()
    large = table.drop_duplicates(["annee", "niveau_geo", "entite_pcode", "age", "sexe"]).pivot_table(
        index=["annee", "niveau_geo", "entite_pcode", "age"], columns="sexe", values="population")
    e2 = (large["G"] + large["F"] - large["T"]).abs()
    unique = table.drop_duplicates(["annee", "niveau_geo", "entite_pcode", "age", "sexe"])
    province_de = communes.set_index("commune_pcode")["province_pcode"]
    com = unique[unique["niveau_geo"] == "commune"]
    s_com = com.assign(p=com["entite_pcode"].map(province_de)).groupby(["annee", "p", "age", "sexe"])["population"].sum()
    prov = unique[unique["niveau_geo"] == "province"].set_index(["annee", "entite_pcode", "age", "sexe"])["population"]
    prov.index = prov.index.set_names(["annee", "p", "age", "sexe"])
    c3 = s_com.index.intersection(prov.index)
    e3 = (s_com.loc[c3] - prov.loc[c3]).abs()
    s_prov = unique[unique["niveau_geo"] == "province"].groupby(["annee", "age", "sexe"])["population"].sum()
    pays = unique[(unique["niveau_geo"] == "pays") & (unique["annee"] >= 2020)].set_index(["annee", "age", "sexe"])[
        "population"]
    c4 = s_prov.index.intersection(pays.index)
    e4 = (s_prov.loc[c4] - pays.loc[c4]).abs() / pays.loc[c4]
    rgph = vie[vie["niveau_geo"] == "commune"].set_index("entite_pcode")["population"]
    p2020 = com[(com["annee"] == 2020) & (com["sexe"] == "T")].groupby("entite_pcode")["population"].sum()
    rapport = (p2020 / rgph.reindex(p2020.index)).dropna()
    n_com, n_prov = com["entite_pcode"].nunique(), unique.loc[unique["niveau_geo"] == "province", "entite_pcode"].nunique()
    return {
        "population_ages_egal_total_publie": (bool((e1 <= 1).mean() >= 0.99),
                                              f"{int((e1 <= 1).sum())} tableaux × années × sexes sur {len(e1)}"),
        "population_garcons_plus_filles": (bool((e2 <= 1).mean() >= 0.99), f"{int((e2 <= 1).sum())} lignes sur {len(e2)}"),
        "population_communes_egal_province": (bool((e3 <= 1).mean() >= 0.99) and len(e3) > 0,
                                              f"{int((e3 <= 1).sum())} province × année × âge × sexe sur {len(e3)}"),
        "population_provinces_egal_pays": (bool((e4 <= 0.001).mean() >= 0.95),
                                           f"2020-2035 : {int((e4 <= 0.001).sum())} sur {len(e4)} à 0,1 % près"),
        "population_couverture": (n_com == communes["commune_pcode"].nunique() and n_prov == 47,
                                  f"{n_com} communes, {n_prov} provinces de 2025, pays de "
                                  f"{int(table['annee'].min())} à {int(table['annee'].max())}"),
        "population_2020_proche_rgph_2019": (bool(0.95 <= rapport.median() <= 1.10),
                                             f"population 2020 / RGPH 2019 par commune : médiane {rapport.median():.3f}"),
    }
