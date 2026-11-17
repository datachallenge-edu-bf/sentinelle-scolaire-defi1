"""Brique 2 : pourquoi une province a un niveau habituel d'abandon élevé.

Unité : la province (ensemble) ou la province × sexe. Cible : le taux d'abandon moyen observé
hors ruptures (le niveau habituel, qui est aussi la prévision retenue). Variables : leur moyenne
sur les années de la province, sans les variables de persistance (expliquer le niveau par le
niveau passé serait circulaire).

Les modèles sont validés en prédisant des provinces qu'ils n'ont pas vues (validation croisée par
groupes de provinces : les deux sexes d'une province restent ensemble). L'explication a deux volets :

- effets chiffrés : l'elastic net le mieux validé (nombre de variables choisi par validation) donne
  l'effet de chaque variable en points de taux d'abandon, dénormalisé en unités d'origine ;
- facteurs de chaque province : LightGBM sur les variables gardées par l'élimination récursive
  guidée par SHAP (module ``elimination``) ; les valeurs SHAP donnent la contribution de chaque
  variable au niveau de chaque province.

Les liens décrits sont des associations, pas des causes.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
from scipy.stats import spearmanr
from sklearn.linear_model import ElasticNetCV
from sklearn.model_selection import GroupKFold

from . import elimination as EL
from . import preparation as P
from .libelles import libelle

EXCLUES = set(P.PERSISTANCE) | {P.CIBLE, "ruptures_passees", "baisse_effectifs"}
PARAMETRES_LGB = dict(n_estimators=300, learning_rate=0.03, num_leaves=4, max_depth=2, min_child_samples=5,
                      subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0, verbose=-1,
                      random_state=42, n_jobs=1)
PLIS_GROUPES = 5
GRILLE_K = [5, 8, 12, None]


def table_niveaux(d: pd.DataFrame, t: pd.DataFrame, entite: list[str], variables: list[str]):
    """Variables moyennes de chaque unité et niveau habituel observé (vide pour les provinces sans cible observée)."""
    variables = [v for v in variables if v not in EXCLUES]
    identifiants = d.groupby(entite)[["province_nom", "region_nom", "methode_passage"]].first()
    x = d.groupby(entite)[variables].mean()
    y = t[t["apprenable"]].groupby(entite)["y"].mean().rename("niveau_habituel_observe")
    return identifiants.join(x).join(y), variables


def _standardiser(xa: pd.DataFrame, xt: pd.DataFrame):
    mediane = xa.median()
    xa, xt = xa.fillna(mediane), xt.fillna(mediane)
    moyenne, ecart = xa.mean(), xa.std().replace(0, 1)
    return (xa - moyenne) / ecart, (xt - moyenne) / ecart


def _ajuster(modele: str, xa, ya, xt):
    """Prévisions et contributions par variable (points de taux d'abandon)."""
    if modele == "lightgbm":
        m = lgb.LGBMRegressor(**PARAMETRES_LGB).fit(xa, ya)
        return m.predict(xt), pd.DataFrame(shap.TreeExplainer(m).shap_values(xt), columns=xt.columns, index=xt.index)
    sa, st = _standardiser(xa, xt)
    m = ElasticNetCV(l1_ratio=0.5, cv=5, max_iter=50000, random_state=42).fit(sa, ya)
    return m.predict(st), pd.DataFrame(st.values * m.coef_, columns=st.columns, index=st.index)


def _rang(x: pd.DataFrame, y: pd.Series) -> list[str]:
    """Variables par contribution SHAP absolue moyenne d'un LightGBM appris sur (x, y)."""
    _, contrib = _ajuster("lightgbm", x, y, x)
    return list(contrib.abs().mean().sort_values(ascending=False).index)


def _choisir(rang: list[str], k) -> list[str]:
    return rang if k is None else rang[:k]


def valider(niveaux: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    """Part de variance expliquée et corrélation de rang sur des provinces non vues, pour chaque modèle et
    chaque nombre k de variables ; le classement des variables est refait dans chaque pli."""
    connus = niveaux[niveaux["niveau_habituel_observe"].notna()]
    x, y = connus[variables], connus["niveau_habituel_observe"]
    groupes = connus.index.get_level_values("province_pcode")
    decoupes = list(GroupKFold(PLIS_GROUPES).split(x, y, groupes))
    rangs = [_rang(x.iloc[a], y.iloc[a]) for a, _ in decoupes]
    lignes = []
    for modele in ["lightgbm", "elastic_net"]:
        for k in GRILLE_K:
            prevu = pd.Series(np.nan, index=connus.index)
            for (a, b), rang in zip(decoupes, rangs):
                v = _choisir(rang, k)
                prevu.iloc[b], _ = _ajuster(modele, x.iloc[a][v], y.iloc[a], x.iloc[b][v])
            r2 = 1 - ((y - prevu) ** 2).sum() / ((y - y.mean()) ** 2).sum()
            lignes.append({"modele": modele, "k": k if k else len(variables), "unites": len(y),
                           "r2_provinces_non_vues": round(float(r2), 3),
                           "correlation_rang_provinces_non_vues": round(float(spearmanr(y, prevu).statistic), 3),
                           "erreur_absolue_moyenne": round(float((y - prevu).abs().mean()), 3)})
    return pd.DataFrame(lignes)


def expliquer(niveaux: pd.DataFrame, variables: list[str], modele: str):
    """Contributions de chaque variable au niveau de chaque unité (provinces scindées comprises)."""
    connus = niveaux[niveaux["niveau_habituel_observe"].notna()]
    prevu, contrib = _ajuster(modele, connus[variables], connus["niveau_habituel_observe"], niveaux[variables])
    return pd.Series(prevu, index=niveaux.index, name="niveau_explique"), contrib


def effets_lineaires(niveaux: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    """Effet de chaque variable sur le niveau habituel (points de taux), par l'elastic net : coefficient
    standardisé dénormalisé (divisé par l'écart-type de la variable), pour un point de pourcentage d'une part
    ou une unité des autres variables."""
    connus = niveaux[niveaux["niveau_habituel_observe"].notna()]
    x = connus[variables].fillna(connus[variables].median())
    ecart = x.std().replace(0, 1)
    m = ElasticNetCV(l1_ratio=0.5, cv=5, max_iter=50000, random_state=42).fit((x - x.mean()) / ecart,
                                                                              connus["niveau_habituel_observe"])
    # Les parts (entre 0 et 1) se lisent par point de pourcentage, les autres variables par unité.
    part = (x.max() <= 1.0001) & (x.min() >= 0)
    par_unite = m.coef_ / ecart.values
    t = pd.DataFrame({"variable": variables, "libelle": [libelle(v) for v in variables],
                      "effet_pour_un_ecart_type_points": np.round(m.coef_, 3),
                      "ecart_type_de_la_variable": np.round(ecart.values, 4),
                      "unite": np.where(part, "point de pourcentage", "unité de la variable"),
                      "effet_par_unite_points": np.round(np.where(part, par_unite / 100, par_unite), 4)})
    return t[t["effet_pour_un_ecart_type_points"] != 0].sort_values(
        "effet_pour_un_ecart_type_points", key=abs, ascending=False).reset_index(drop=True)


def facteurs(contrib: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Les n variables qui poussent le plus le niveau vers le haut et celle qui le freine le plus."""
    lignes = []
    for cle, r in contrib.iterrows():
        hausse = r[r > 0].sort_values(ascending=False).head(n)
        baisse = r[r < 0].sort_values().head(1)
        ligne = {f"facteur_{k + 1}": f"{libelle(v)} (+{c:.1f} pt)" for k, (v, c) in enumerate(hausse.items())}
        if not len(hausse):
            ligne["facteur_1"] = "aucun facteur au-dessus de la moyenne des provinces"
        ligne["frein_principal"] = f"{libelle(baisse.index[0])} ({baisse.iloc[0]:.1f} pt)" if len(baisse) else ""
        lignes.append(ligne)
    return pd.DataFrame(lignes, index=contrib.index)


def importance(contrib: pd.DataFrame, niveaux: pd.DataFrame) -> pd.DataFrame:
    """Contribution absolue moyenne et sens du lien (une valeur plus élevée augmente-t-elle le niveau ?)."""
    lignes = []
    for v in contrib.columns:
        x = niveaux[v]
        sens = spearmanr(x, contrib[v], nan_policy="omit").statistic if x.nunique() > 1 else np.nan
        lignes.append({"variable": v, "libelle": libelle(v),
                       "contribution_absolue_moyenne_points": round(float(contrib[v].abs().mean()), 3),
                       "sens": "plus elle est élevée, plus le risque est élevé" if sens > 0.2 else
                       ("plus elle est élevée, plus le risque est faible" if sens < -0.2 else "lien non monotone")})
    return pd.DataFrame(lignes).sort_values("contribution_absolue_moyenne_points", ascending=False).reset_index(drop=True)


def _elastic_final(connus: pd.DataFrame, variables: list[str]):
    """Elastic net appris sur toutes les unités connues, avec ses paramètres de normalisation."""
    x = connus[variables]
    mediane = x.median()
    x = x.fillna(mediane)
    moyenne, ecart = x.mean(), x.std().replace(0, 1)
    m = ElasticNetCV(l1_ratio=0.5, cv=5, max_iter=50000, random_state=42).fit(
        (x - moyenne) / ecart, connus["niveau_habituel_observe"])
    return m, {"mediane": mediane.to_dict(), "moyenne": moyenne.to_dict(), "ecart_type": ecart.to_dict()}


def executer(d, t, entite, variables) -> tuple[dict[str, pd.DataFrame], dict]:
    niveaux, variables = table_niveaux(d, t, entite, variables)
    validation = valider(niveaux, variables)
    connus = niveaux[niveaux["niveau_habituel_observe"].notna()]
    x, y = connus[variables], connus["niveau_habituel_observe"]

    # Volet 1 : effets chiffrés par l'elastic net le mieux validé.
    lineaire = validation[validation["modele"] == "elastic_net"].sort_values(
        ["r2_provinces_non_vues", "k"], ascending=[False, True]).iloc[0]
    k_lineaire = int(lineaire["k"])
    variables_lineaires = _rang(x, y)[:k_lineaire]
    elastic, normalisation = _elastic_final(connus, variables_lineaires)

    # Volet 2 : facteurs de chaque province par LightGBM après élimination récursive guidée par SHAP.
    courbe = EL.courbe_explication(x, y, connus.index.get_level_values("province_pcode"), PARAMETRES_LGB, PLIS_GROUPES)
    admissibles = courbe[courbe["r2_provinces_non_vues"] >= courbe["r2_provinces_non_vues"].max() - 0.01]
    optimum = admissibles.sort_values("nombre_de_variables").iloc[0]
    n_arbres = int(optimum["nombre_de_variables"])
    variables_arbres = EL.variables_explication(x, y, n_arbres, PARAMETRES_LGB)
    arbres = lgb.LGBMRegressor(**PARAMETRES_LGB).fit(x[variables_arbres], y)
    contrib = pd.DataFrame(shap.TreeExplainer(arbres).shap_values(niveaux[variables_arbres]),
                           columns=variables_arbres, index=niveaux.index)
    prevu = pd.Series(arbres.predict(niveaux[variables_arbres]), index=niveaux.index, name="niveau_explique")

    validation = pd.concat([validation, pd.DataFrame([{
        "modele": "lightgbm_elimination", "k": n_arbres, "unites": len(y),
        "r2_provinces_non_vues": optimum["r2_provinces_non_vues"], "correlation_rang_provinces_non_vues": np.nan,
        "erreur_absolue_moyenne": optimum["erreur_absolue_moyenne"]}])], ignore_index=True)
    validation["role"] = ""
    validation.loc[(validation["modele"] == "elastic_net") & (validation["k"] == k_lineaire), "role"] = "effets chiffrés"
    validation.loc[validation["modele"] == "lightgbm_elimination", "role"] = "facteurs par province"

    sortie = niveaux[["province_nom", "region_nom", "niveau_habituel_observe"]].join(prevu.round(2)).join(
        facteurs(contrib))
    valeurs = niveaux[["province_nom", "region_nom", "niveau_habituel_observe"] + variables_arbres].reset_index()
    base_shap = float(np.ravel(shap.TreeExplainer(arbres).expected_value)[0])
    tables = {"validation": validation, "courbe_elimination": courbe, "facteurs": sortie.reset_index(),
              "valeurs": valeurs, "valeur_de_base": pd.DataFrame([{"valeur_de_base_shap": round(base_shap, 4)}]),
              "importance": importance(contrib, niveaux), "contributions": contrib.round(3).reset_index(),
              "effets_lineaires": effets_lineaires(niveaux, variables_lineaires),
              "variables_retenues": pd.DataFrame(
                  [{"volet": "effets chiffrés (elastic net)", "rang": i + 1, "variable": v, "libelle": libelle(v)}
                   for i, v in enumerate(variables_lineaires)]
                  + [{"volet": "facteurs par province (LightGBM)", "rang": i + 1, "variable": v, "libelle": libelle(v)}
                     for i, v in enumerate(variables_arbres)])}
    objets = {"lightgbm": arbres, "variables_lightgbm": variables_arbres, "elastic_net": elastic,
              "variables_elastic_net": variables_lineaires, "normalisation_elastic_net": normalisation,
              "r2_lightgbm": float(optimum["r2_provinces_non_vues"]),
              "r2_elastic_net": float(lineaire["r2_provinces_non_vues"])}
    return tables, objets
