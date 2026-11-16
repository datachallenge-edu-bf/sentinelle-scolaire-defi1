"""Brique 1 : prévision du taux d'abandon du primaire à 1, 2 et 3 ans, avec un intervalle calibré.

Six modèles sont comparés dans le temps (module ``preparation``) :

- références : taux de l'année t ; niveau habituel de la province (moyenne passée hors ruptures) ;
- régression elastic net ;
- régression ridge avec un effet par province (équivalent pénalisé d'un modèle mixte) ;
- LightGBM en régression quantile (10 %, 50 %, 90 %), arbres courts et régularisés ;
- moyenne de l'elastic net et de LightGBM.

Les modèles appris prédisent l'écart au niveau habituel de la province, diminué du choc commun à
toutes les provinces l'année de la cible (crise nationale), qu'aucune variable provinciale ne
prévoit. Le modèle retenu est celui de plus petite erreur moyenne sur les plis de sélection,
références comprises : un modèle complexe n'est gardé que s'il fait mieux que les références.

Intervalle à 80 % : prédiction conforme sur les erreurs hors échantillon des plis (quantiles
conformalisés pour LightGBM, écart absolu sinon), couverture vérifiée sur le test final.
"""

from __future__ import annotations

import math

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet, Ridge

from . import preparation as P

NIVEAU = 0.80
QUANTILES = {"q10": 0.10, "q50": 0.50, "q90": 0.90}
GRILLE_ELASTIC = [0.1, 0.3, 1.0, 3.0, 10.0]
GRILLE_RIDGE = [30.0, 100.0, 300.0, 1000.0, 3000.0]
PARAMETRES_LGB = dict(n_estimators=400, learning_rate=0.03, num_leaves=7, max_depth=3, min_child_samples=15,
                      subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=2.0, verbose=-1,
                      random_state=42, n_jobs=1)
BASE = "moyenne_passee_abandon"
MODELES = ["reference_annee_precedente", "reference_niveau_habituel", "elastic_net", "ridge_effet_province",
           "lightgbm", "moyenne_elastic_lightgbm"]
# Par ordre de simplicité : en cas d'égalité, le plus simple l'emporte.
SIMPLICITE = {m: i for i, m in enumerate(MODELES)}
SEUIL_HAUSSE = 2.0


def _ecart_a_apprendre(train: pd.DataFrame) -> pd.Series:
    ecart = train["y"] - train[BASE]
    return ecart - ecart.groupby(train["annee_cible"]).transform("mean")


def elastic(train, test, variables, alpha):
    xa, xt = P.matrice_lineaire(train, test, variables)
    m = ElasticNet(alpha=alpha, l1_ratio=0.5, max_iter=20000, random_state=42)
    m.fit(xa, _ecart_a_apprendre(train), sample_weight=train["poids"])
    return m.predict(xt) + test[BASE].values, m


def ridge_province(train, test, variables, alpha):
    xa, xt = P.matrice_lineaire(train, test, variables)
    for p in sorted(set(train["province_pcode"])):
        xa[f"province_{p}"] = (train["province_pcode"] == p).astype(float)
        xt[f"province_{p}"] = (test["province_pcode"] == p).astype(float)
    m = Ridge(alpha=alpha)
    m.fit(xa, _ecart_a_apprendre(train), sample_weight=train["poids"])
    return m.predict(xt) + test[BASE].values


def lightgbm_quantiles(train, test, variables):
    sorties = {}
    for nom, q in QUANTILES.items():
        m = lgb.LGBMRegressor(objective="quantile", alpha=q, **PARAMETRES_LGB)
        m.fit(train[variables].astype(float), _ecart_a_apprendre(train), sample_weight=train["poids"])
        sorties[nom] = m.predict(test[variables].astype(float)) + test[BASE].values
    return sorties["q50"], np.minimum(sorties["q10"], sorties["q90"]), np.maximum(sorties["q10"], sorties["q90"])


def predire(train, test, lineaire, arbres, reglages) -> dict[str, np.ndarray]:
    p = {"reference_annee_precedente": test[P.CIBLE].values, "reference_niveau_habituel": test[BASE].values}
    p["elastic_net"], _ = elastic(train, test, lineaire, reglages["alpha_elastic"])
    p["ridge_effet_province"] = ridge_province(train, test, lineaire, reglages["alpha_ridge"])
    p["lightgbm"], p["lightgbm_bas"], p["lightgbm_haut"] = lightgbm_quantiles(train, test, arbres)
    p["moyenne_elastic_lightgbm"] = (p["elastic_net"] + p["lightgbm"]) / 2
    return p


def choisir_reglages(t, lineaire, nom) -> dict:
    """Pénalités de l'elastic net et de la ridge choisies sur les plis de sélection."""
    erreurs_e, erreurs_r = {a: [] for a in GRILLE_ELASTIC}, {a: [] for a in GRILLE_RIDGE}
    for _, train, test in P.plis(t, P.PLIS[nom], 1):
        for a in GRILLE_ELASTIC:
            erreurs_e[a].append(np.mean(np.abs(test["y"] - elastic(train, test, lineaire, a)[0])))
        for a in GRILLE_RIDGE:
            erreurs_r[a].append(np.mean(np.abs(test["y"] - ridge_province(train, test, lineaire, a))))
    return {"alpha_elastic": min(erreurs_e, key=lambda a: np.mean(erreurs_e[a])),
            "alpha_ridge": min(erreurs_r, key=lambda a: np.mean(erreurs_r[a]))}


def evaluer(t, lineaire, arbres, reglages, entite, nom, horizon):
    """Prévisions hors échantillon de chaque pli et du test final, et leurs mesures."""
    lignes, previsions = [], []
    for annee, train, test in P.plis(t, P.PLIS[nom] + [P.TEST_FINAL[nom]], horizon):
        p = predire(train, test, lineaire, arbres, reglages)
        role = "test final" if annee == P.TEST_FINAL[nom] else "sélection"
        for m in MODELES:
            lignes.append({"horizon": horizon, "annee_cible": annee, "role": role, "modele": m,
                           "lignes_apprentissage": len(train), "lignes_test": len(test),
                           **P.mesures(test["y"].values, p[m])})
        previsions.append(test[entite + ["annee_scolaire", "annee_cible", "y"]].assign(
            role=role, **{m: p[m] for m in MODELES + ["lightgbm_bas", "lightgbm_haut"]}))
    if not lignes:
        return pd.DataFrame(), pd.DataFrame()
    return pd.DataFrame(lignes), pd.concat(previsions, ignore_index=True)


def synthese(evaluation: pd.DataFrame) -> pd.DataFrame:
    colonnes = ["erreur_absolue_moyenne", "correlation_rang", "rappel_quintile_le_plus_a_risque"]
    return evaluation.groupby(["horizon", "role", "modele"])[colonnes].mean().round(3).reset_index()


def choisir_modele(evaluation: pd.DataFrame) -> str:
    """Plus petite erreur moyenne sur les plis de sélection, références comprises ; le plus simple en cas d'égalité."""
    s = evaluation[evaluation["role"] == "sélection"].groupby("modele")["erreur_absolue_moyenne"].mean().round(2)
    meilleurs = s[s == s.min()].index
    return min(meilleurs, key=SIMPLICITE.get)


def marge_conforme(prev: pd.DataFrame, modele: str) -> float:
    """Marge de l'intervalle à 80 % : quantile conformalisé des scores de non-conformité."""
    if modele == "lightgbm":
        score = np.maximum(prev["lightgbm_bas"] - prev["y"], prev["y"] - prev["lightgbm_haut"])
    else:
        score = (prev["y"] - prev[modele]).abs()
    n = len(score)
    return float(np.quantile(score, min(1.0, math.ceil((n + 1) * NIVEAU) / n)))


def intervalle(point, bas_q, haut_q, modele, marge):
    if modele == "lightgbm":
        return bas_q - marge, haut_q + marge
    return point - marge, point + marge


def prevoir(d, t, nom, lineaire, arbres, reglages, modele, marge, horizon, annees_x) -> pd.DataFrame:
    """Modèle retenu, appris sur toutes les cibles apprenables, appliqué aux variables des années ``annees_x``."""
    train = t[t["apprenable"]]
    x = d[d["annee_scolaire"].isin(annees_x)].copy()
    p = predire(train, x, lineaire, arbres, reglages)
    bas, haut = intervalle(p[modele], p["lightgbm_bas"], p["lightgbm_haut"], modele, marge)
    seuils = train["y"].quantile([0.5, 0.8]).values
    sortie = x[["province_pcode", "province_nom", "region_nom", "province_ancienne_nom", "methode_passage"]
               + (["sexe"] if nom == "sexe" else []) + ["annee_scolaire", P.CIBLE]].rename(
        columns={"annee_scolaire": "annee_des_variables", P.CIBLE: "taux_abandon_annee_des_variables"})
    sortie["province_scindee"] = sortie.pop("methode_passage").str.startswith("province scindée")
    sortie["annee_prevue"] = x["annee_scolaire"].map(lambda a: P.annee_plus(a, horizon))
    sortie["horizon"] = horizon
    sortie["modele"] = modele
    sortie["taux_abandon_prevu"] = np.round(p[modele], 2)
    sortie["borne_basse_80"] = np.round(bas, 2)
    sortie["borne_haute_80"] = np.round(haut, 2)
    sortie["classe_de_risque"] = np.select([p[modele] >= seuils[1], p[modele] >= seuils[0]], ["élevé", "moyen"],
                                           "faible")
    # Prévision nettement au-dessus du taux de l'année des variables (retour vers un niveau habituel plus élevé).
    sortie["prevision_au_dessus_du_taux_actuel"] = (p[modele] - x[P.CIBLE].values) > SEUIL_HAUSSE
    return sortie.reset_index(drop=True), seuils


def couverture(prev_test: pd.DataFrame, modele: str, marge: float, horizon: int) -> dict:
    bas, haut = intervalle(prev_test[modele], prev_test["lightgbm_bas"], prev_test["lightgbm_haut"], modele, marge)
    dedans = (prev_test["y"] >= bas) & (prev_test["y"] <= haut)
    return {"horizon": horizon, "modele": modele, "marge_conforme": round(marge, 3),
            "couverture_test_final": round(float(dedans.mean()), 3),
            "largeur_moyenne": round(float(np.mean(haut - bas)), 3), "lignes": len(prev_test)}
