"""Préparation commune aux trois briques du modèle : table des variables de l'année t, cible de
l'horizon h, plis de la validation dans le temps et mesures de qualité.

Une ligne : les variables de l'année t (X) et le taux d'abandon du primaire entre t+h-1 et t+h
(y). Seules les cibles observées hors rupture de scolarisation sont « apprenables ».

Plis : pour une cible de l'année Y, l'apprentissage n'utilise que des cibles connues à la date
des variables, soit des années au plus égales à Y − h. Les trois premiers plis servent aux
choix ; le test final n'est utilisé qu'une fois.

Variables du post-primaire (observées une année sur deux) : leurs valeurs imputées dans la base
apurée utilisent parfois des années postérieures ; elles sont remises à vide puis complétées par
la dernière valeur observée, qui ne dépend que du passé.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from ..apurement import par_sexe
from ..apurement.etat import OBSERVEE, SOURCE_INSD
from . import exploration as E

CIBLE = E.CIBLE
DERNIERE_ANNEE = "2024-2025"
PLIS = {"ensemble": ["2021-2022", "2022-2023", "2023-2024"], "sexe": ["2020-2021", "2021-2022", "2022-2023"]}
TEST_FINAL = {"ensemble": "2024-2025", "sexe": "2023-2024"}
PERSISTANCE = ["moyenne_passee_abandon", "ecart_abandon_a_la_moyenne", "rupture_annee_precedente"]


def annee_plus(annee: str, ecart: int) -> str:
    return E.annee_plus(annee, ecart)


def statut_source(jeu: dict, nom: str):
    """Fonction (province, sexe, année, variable) -> statut de la cellule dans la base apurée."""
    st = jeu["statuts"].set_index(["province_pcode", "annee_scolaire", "variable"])["statut"].to_dict()
    st_sexe = {}
    if nom == "sexe":
        st_sexe = jeu["statuts_sexe"].set_index(["province_pcode", "sexe", "annee_scolaire", "variable"])[
            "statut"].to_dict()

    def statut(p, s, a, v):
        if nom == "sexe" and v in par_sexe.PAR_SEXE:
            return st_sexe.get((p, s, a, v))
        return st.get((p, a, v))
    return statut


def preparer(jeu: dict, nom: str, listes: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Table de toutes les années, avec les variables de persistance et le post-primaire ramené au passé.

    Renvoie la table, la liste des variables des modèles linéaires et celle des modèles d'arbres.
    """
    entite = jeu["entite"]
    d = jeu["base"].sort_values(entite + ["annee_scolaire"]).reset_index(drop=True).copy()
    lineaire = listes.loc[listes["liste_lineaire"], "variable"].tolist()
    arbres = listes.loc[listes["liste_arbres"], "variable"].tolist()
    part = listes.set_index("variable")["part_observee"]
    statut = statut_source(jeu, nom)
    sexe = d["sexe"] if "sexe" in d else pd.Series("", index=d.index)
    groupes = [d[c] for c in entite]
    for v in [v for v in arbres if part.get(v, 1) < E.SEUIL_OBSERVEE_ARBRES]:
        garde = [statut(p, s, a, v) in (OBSERVEE, SOURCE_INSD)
                 for p, s, a in zip(d["province_pcode"], sexe, d["annee_scolaire"])]
        d[v] = d[v].where(garde).groupby(groupes).ffill()
    # Niveau habituel : moyenne des abandons passés de la province, années de rupture exclues.
    d["rupture_annee_precedente"] = (d["evolution_eleves_primaire"].abs() > E.SEUIL_RUPTURE).astype(float)
    propre = d[CIBLE].where(d["rupture_annee_precedente"] == 0)
    somme = propre.fillna(0).groupby(groupes).cumsum()
    nombre = propre.notna().astype(int).groupby(groupes).cumsum()
    tout = d[CIBLE].groupby(groupes).transform(lambda s: s.expanding().mean())
    d["moyenne_passee_abandon"] = (somme / nombre.replace(0, np.nan)).fillna(tout)
    d["ecart_abandon_a_la_moyenne"] = d[CIBLE] - d["moyenne_passee_abandon"]
    d["ruptures_passees"] = d["rupture_annee_precedente"].groupby(groupes).cumsum()
    d["baisse_effectifs"] = (-d["evolution_eleves_primaire"]).clip(lower=0)
    d["poids"] = np.sqrt(d["eleves_primaire"].clip(lower=1))
    return d, lineaire + PERSISTANCE, arbres + PERSISTANCE


def avec_cible(d: pd.DataFrame, jeu: dict, nom: str, horizon: int) -> pd.DataFrame:
    """Ajoute la cible de l'horizon h : taux d'abandon entre t+h-1 et t+h, son statut, la rupture éventuelle."""
    entite = jeu["entite"]
    t = d.copy()
    t["annee_cible"] = t["annee_scolaire"].map(lambda a: annee_plus(a, horizon))
    t["y"] = t.groupby(entite)[CIBLE].shift(-horizon)
    statut = statut_source(jeu, nom)
    sexe = t["sexe"] if "sexe" in t else pd.Series("", index=t.index)
    t["y_observee"] = [statut(p, s, a, CIBLE) == OBSERVEE
                       for p, s, a in zip(t["province_pcode"], sexe, t["annee_cible"])]
    evolution = jeu["base"].groupby(["province_pcode", "annee_scolaire"])["evolution_eleves_primaire"].first()
    t["evolution_vers_cible"] = [evolution.get((p, a), np.nan) for p, a in zip(t["province_pcode"], t["annee_cible"])]
    t["rupture_cible"] = t["evolution_vers_cible"].abs() > E.SEUIL_RUPTURE
    t["apprenable"] = t["y"].notna() & t["y_observee"] & ~t["rupture_cible"]
    return t


def plis(t: pd.DataFrame, annees: list[str], horizon: int, colonne: str = "apprenable"):
    """(année de la cible, apprentissage, test) pour chaque année, si l'apprentissage couvre au moins deux années."""
    for annee in annees:
        test = t[t[colonne] & (t["annee_cible"] == annee)]
        train = t[t[colonne] & (t["annee_cible"] <= annee_plus(annee, -horizon))]
        if len(test) and train["annee_cible"].nunique() >= 2:
            yield annee, train, test


def matrice_lineaire(train: pd.DataFrame, test: pd.DataFrame, variables: list[str]):
    """Variables standardisées ; valeurs manquantes remplacées par la médiane de l'apprentissage, avec un indicateur."""
    xa, xt = train[variables].astype(float), test[variables].astype(float)
    for v in [v for v in variables if xa[v].isna().any() or xt[v].isna().any()]:
        xa[f"{v}__manquante"], xt[f"{v}__manquante"] = xa[v].isna().astype(float), xt[v].isna().astype(float)
    mediane = xa.median()
    xa, xt = xa.fillna(mediane).fillna(0), xt.fillna(mediane).fillna(0)
    moyenne, ecart = xa.mean(), xa.std().replace(0, 1)
    return (xa - moyenne) / ecart, (xt - moyenne) / ecart


def mesures(y: np.ndarray, prevision: np.ndarray) -> dict[str, float]:
    """Erreur absolue moyenne (points), corrélation de rang, part du quintile le plus à risque retrouvée."""
    k = max(1, math.ceil(0.2 * len(y)))
    vrais, prevus = set(np.argsort(-y)[:k]), set(np.argsort(-prevision)[:k])
    return {"erreur_absolue_moyenne": float(np.mean(np.abs(y - prevision))),
            "correlation_rang": float(spearmanr(y, prevision).statistic),
            "rappel_quintile_le_plus_a_risque": len(vrais & prevus) / k}
