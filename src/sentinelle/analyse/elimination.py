"""Élimination récursive des variables guidée par les valeurs SHAP.

À chaque étape, LightGBM est appris sur les variables restantes, les variables sont classées par
contribution SHAP absolue moyenne, et les moins importantes sont retirées (10 % des restantes, au
moins une). La performance est mesurée à chaque étape ; le nombre de variables retenu est le plus
petit dont la performance reste à moins de 1 % de la meilleure (parcimonie).

Sans fuite d'information :

- prévision : dans chaque pli, le chemin d'élimination et le choix du nombre de variables utilisent
  seulement l'apprentissage du pli (les années antérieures apprennent, la dernière valide) ; le pli
  de test mesure ensuite le modèle appris avec les variables choisies ;
- explication : pour chaque groupe de provinces mis de côté, le chemin est calculé sur les autres
  provinces ; la courbe donne la part de variance expliquée des provinces non vues selon le nombre
  de variables.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
from sklearn.model_selection import GroupKFold

from . import preparation as P

PART_RETIREE = 0.10
TOLERANCE = 0.01
MINIMUM = 3


def _importance(modele, x: pd.DataFrame) -> pd.Series:
    valeurs = shap.TreeExplainer(modele).shap_values(x)
    return pd.Series(np.abs(valeurs).mean(axis=0), index=x.columns)


def chemin(ajuster, x: pd.DataFrame, y: pd.Series, mesurer, poids=None) -> list[tuple[list[str], float]]:
    """Étapes (variables, performance) de l'élimination ; ``ajuster`` renvoie un LightGBM appris,
    ``mesurer(variables, modele)`` une erreur (plus petit = meilleur)."""
    restantes = list(x.columns)
    etapes = []
    while True:
        m = ajuster(x[restantes], y, poids)
        etapes.append((list(restantes), mesurer(restantes, m)))
        if len(restantes) <= MINIMUM:
            return etapes
        importance = _importance(m, x[restantes]).sort_values()
        retirer = max(1, int(round(PART_RETIREE * len(restantes))))
        retirer = min(retirer, len(restantes) - MINIMUM)
        restantes = [v for v in restantes if v not in set(importance.index[:retirer])]


def choisir(etapes: list[tuple[list[str], float]]) -> list[str]:
    """Le plus petit ensemble dont l'erreur reste à moins de 1 % de la meilleure."""
    meilleure = min(e for _, e in etapes)
    admissibles = [v for v, e in etapes if e <= meilleure * (1 + TOLERANCE)]
    return min(admissibles, key=len)


# Prévision (LightGBM sur l'échelle logit, écart au niveau habituel).

def variables_prevision(train: pd.DataFrame, variables: list[str], params: dict, relative, lgb_fabrique):
    """Variables choisies par élimination, avec la seule information de ``train``."""
    derniere = train["annee_cible"].max()
    a, v = train[train["annee_cible"] < derniere], train[train["annee_cible"] == derniere]

    def ajuster(x, y, poids):
        return lgb_fabrique(params).fit(x.astype(float), y, sample_weight=poids)

    def mesurer(vars_, m):
        z = m.predict(v[vars_].astype(float)) + v["base_z"].values
        return float(np.mean(np.abs(v["y"].values - P.denormaliser(z))))

    etapes = chemin(ajuster, a[variables], relative(a), mesurer, a["poids"])
    return choisir(etapes), etapes


# Explication (niveau habituel, provinces non vues).

def courbe_explication(x: pd.DataFrame, y: pd.Series, groupes, params: dict, plis: int = 5) -> pd.DataFrame:
    """Part de variance expliquée des provinces non vues selon le nombre de variables."""
    previsions = {}
    for a, b in GroupKFold(plis).split(x, y, groupes):
        def ajuster(xx, yy, _):
            return lgb.LGBMRegressor(**params).fit(xx, yy)

        def mesurer(vars_, m):
            previsions.setdefault(len(vars_), pd.Series(np.nan, index=y.index))
            previsions[len(vars_)].iloc[b] = m.predict(x.iloc[b][vars_])
            return 0.0
        chemin(ajuster, x.iloc[a], y.iloc[a], mesurer)
    lignes = []
    for n, prevu in sorted(previsions.items()):
        if prevu.isna().any():
            continue
        r2 = 1 - ((y - prevu) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        lignes.append({"nombre_de_variables": n, "r2_provinces_non_vues": round(float(r2), 4),
                       "erreur_absolue_moyenne": round(float((y - prevu).abs().mean()), 4)})
    return pd.DataFrame(lignes)


def variables_explication(x: pd.DataFrame, y: pd.Series, n: int, params: dict) -> list[str]:
    """Chemin d'élimination sur toutes les provinces, arrêté à n variables."""
    etapes = chemin(lambda xx, yy, _: lgb.LGBMRegressor(**params).fit(xx, yy), x, y, lambda v, m: 0.0)
    return min((v for v, _ in etapes if len(v) >= n), key=len)
