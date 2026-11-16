"""Étape 2 : valeurs publiées par l'INSD pour le post-primaire, contrôlées contre le panel.

Les annuaires statistiques régionaux 2024 de l'INSD publient, par province, le TBS du
post-primaire par sexe et le taux d'achèvement, pour 2016-2017, 2017-2018, 2018-2019,
2022-2023 et 2023-2024. Les valeurs sont transcrites, avec leur document, leurs tableaux et
leur lien, dans ``data/sources_transcrites/insd_post_primaire_province.csv``.

Soum et Tapoa, scindées en 2025, ne sont pas dans le panel : leurs valeurs servent à l'étape 3 pour
les provinces qui en sont issues.

Contrôle : pour chaque province et variable, la valeur INSD est comparée au panel (annuaires
DGESS) en 2018-2019 et en 2022-2023, à 0,6 point près (0,03 pour la parité). Les valeurs de
2016-2017 et 2017-2018 sont retenues si 2018-2019 est conforme, celle de 2023-2024 si 2022-2023
l'est. Restent ensuite : 2023-2024 sans source (report de 2022-2023), 2016-2017 et 2017-2018
(report de l'année suivante) et 2024-2025 (méthode choisie par test sur 2022-2023 et 2023-2024).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .etat import IMPUTEE, SOURCE_INSD, Apurement

VARIABLES = {"tbs_post_primaire_ensemble": "tbs_post_primaire_province",
             "achevement_post_primaire_ensemble": "achevement_post_primaire_province",
             "parite": "parite_tbs_post_primaire_province"}
TOLERANCE = {"tbs_post_primaire_ensemble": 0.6, "achevement_post_primaire_ensemble": 0.6, "parite": 0.03}
ANNEES_CONTROLE = ["2018-2019", "2022-2023"]
CONTROLE_DE = {"2016-2017": "2018-2019", "2017-2018": "2018-2019", "2023-2024": "2022-2023"}
BORNES = {"tbs_post_primaire_province": (0, 150), "achevement_post_primaire_province": (0, 150),
          "parite_tbs_post_primaire_province": (0.2, 3)}


def lire(chemin: Path) -> pd.DataFrame:
    t = pd.read_csv(chemin, sep=";", encoding="utf-8-sig")
    t["parite"] = t["tbs_post_primaire_filles"] / t["tbs_post_primaire_garcons"]
    return t


def _previsions(s: np.ndarray) -> dict[str, float]:
    sortie = {"report année précédente": s[-1], "moyenne des 3 dernières": s[-3:].mean(),
              "médiane des 3 dernières": np.median(s[-3:])}
    if len(s) >= 3:
        sortie["tendance linéaire (3 dernières)"] = np.polyval(np.polyfit(np.arange(3), s[-3:], 1), 3)
    return sortie


class Etape2:
    def __init__(self, etat: Apurement, avant: pd.DataFrame, sources: pd.DataFrame):
        self.etat, self.avant, self.sources = etat, avant, sources
        self.retenues, self.rejetees, self.controles, self.tests_2024 = [], [], [], {}

    def controler(self) -> None:
        """Compare chaque source au panel avant imputation ; retient ou rejette les valeurs des autres années."""
        panel = self.avant.set_index(["province_nom", "annee_scolaire"])
        dans_panel = self.sources["province_annuaire"].isin(self.avant["province_nom"])
        for province, groupe in self.sources[dans_panel].groupby("province_annuaire"):
            g = groupe.set_index("annee_scolaire")
            for colonne, variable in VARIABLES.items():
                conforme = {}
                for annee in ANNEES_CONTROLE:
                    source = g[colonne].get(annee, np.nan)
                    valeur = panel[variable].get((province, annee), np.nan)
                    conforme[annee] = None if pd.isna(source) or pd.isna(valeur) else bool(
                        abs(source - valeur) <= TOLERANCE[colonne])
                    self.controles.append({"province_nom": province, "variable": variable, "annee_scolaire": annee,
                                           "valeur_annuaire": source, "valeur_panel": valeur,
                                           "conforme": conforme[annee]})
                for annee, reference in CONTROLE_DE.items():
                    source = g[colonne].get(annee, np.nan)
                    if pd.isna(source):
                        continue
                    ligne = {"province_nom": province, "annee_scolaire": annee, "variable": variable,
                             "valeur": round(float(source), 4), "region_annuaire": g["region_annuaire"].iloc[0],
                             "document": g["document"].iloc[0], "tableaux": g["tableaux"].iloc[0],
                             "lien": g["lien"].iloc[0]}
                    (self.retenues if conforme[reference] is True else self.rejetees).append(ligne)

    def integrer(self) -> None:
        d, e = self.etat.base, self.etat
        provinces = set(d["province_nom"])
        cellules_imputees: list[tuple[int, str]] = []
        for ligne in self.retenues:
            i = e.ligne(ligne["province_nom"], ligne["annee_scolaire"])
            if not pd.isna(d.at[i, ligne["variable"]]):
                raise ValueError(f"valeur INSD sur une cellule déjà renseignée : {ligne}")
            d.at[i, ligne["variable"]] = ligne["valeur"]
            e.statut[(i, ligne["variable"])] = SOURCE_INSD
            e.noter(2, i, ligne["variable"], "", ligne["valeur"], "valeur publiée INSD",
                    ligne["document"] + (f", tableaux {ligne['tableaux']}" if isinstance(ligne["tableaux"], str) else ""),
                    nature="source")
        scindees = set(d.loc[e.scindee, "province_nom"])
        for variable in VARIABLES.values():
            for province in sorted(provinces - scindees, key=list(d["province_nom"]).index):
                i = {a: e.ligne(province, a) for a in d["annee_scolaire"].unique()}
                if pd.isna(d.at[i["2023-2024"], variable]) and not pd.isna(d.at[i["2022-2023"], variable]):
                    d.at[i["2023-2024"], variable] = d.at[i["2022-2023"], variable]
                    cellules_imputees.append((i["2023-2024"], variable, "report de l'année précédente"))
                for annee, suivante in [("2017-2018", "2018-2019"), ("2016-2017", "2017-2018")]:
                    if pd.isna(d.at[i[annee], variable]) and not pd.isna(d.at[i[suivante], variable]):
                        d.at[i[annee], variable] = d.at[i[suivante], variable]
                        cellules_imputees.append((i[annee], variable, "report de l'année suivante"))
        # 2024-2025 : méthode choisie sur 2022-2023 et 2023-2024.
        annees = sorted(d["annee_scolaire"].unique())
        for variable in VARIABLES.values():
            p = d.pivot(index="province_nom", columns="annee_scolaire", values=variable)
            erreurs: dict[str, list] = {}
            for cible in ["2022-2023", "2023-2024"]:
                k = annees.index(cible)
                for province in p.index:
                    if province in scindees or pd.isna(p.at[province, cible]):
                        continue
                    histoire = p.loc[province, annees[:k]].dropna()
                    if len(histoire) < 3:
                        continue
                    for m, v in _previsions(histoire.to_numpy()).items():
                        erreurs.setdefault(m, []).append(
                            abs(v - p.at[province, cible]) / max(abs(p[cible].dropna().median()), 1e-9))
            scores = {m: float(np.mean(x)) for m, x in erreurs.items()}
            meilleure = min(scores, key=scores.get)
            self.tests_2024[variable] = (meilleure, scores)
            for province in p.index:
                if province in scindees or not pd.isna(p.at[province, "2024-2025"]):
                    continue
                histoire = p.loc[province, annees[:-1]].dropna()
                if len(histoire) < 3:
                    continue
                v = float(np.clip(_previsions(histoire.to_numpy())[meilleure], *BORNES[variable]))
                i = e.ligne(province, "2024-2025")
                d.at[i, variable] = round(v, 4)
                cellules_imputees.append((i, variable, meilleure))
        for i, variable, methode in cellules_imputees:
            e.statut[(i, variable)] = IMPUTEE
            e.imputations_par_ligne[i] = e.imputations_par_ligne.get(i, 0) + 1
            e.statut_ligne[i] = "partielle"
            e.noter(2, i, variable, "", round(float(d.at[i, variable]), 4), methode,
                    "valeur absente des annuaires INSD ou source rejetée au contrôle")
        for ligne in self.retenues:
            i = e.ligne(ligne["province_nom"], ligne["annee_scolaire"])
            if e.statut_ligne[i] == "aucune":
                e.statut_ligne[i] = "complétée par sources INSD"


def executer(etat: Apurement, avant: pd.DataFrame, chemin: Path) -> Etape2:
    etape = Etape2(etat, avant, lire(chemin))
    etape.controler()
    etape.integrer()
    return etape
