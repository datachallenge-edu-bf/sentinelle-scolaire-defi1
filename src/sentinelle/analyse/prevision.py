"""Brique 1 : prévision du taux d'abandon du primaire à 1, 2 et 3 ans, avec un intervalle calibré.

Sept modèles sont comparés dans le temps (module ``preparation``) :

- références : taux de l'année t ; niveau habituel de la province (moyenne passée hors ruptures) ;
  niveau habituel rétréci vers la région ;
- régression elastic net ;
- régression ridge avec un effet par province (équivalent pénalisé d'un modèle mixte) ;
- LightGBM (médiane, et quantiles 10 % et 90 % pour l'intervalle) ;
- LightGBM avec élimination récursive des variables guidée par les valeurs SHAP (module
  ``elimination``), refaite dans chaque pli sur la seule information de l'apprentissage ;
- moyenne de l'elastic net et de LightGBM ;
- retour amorti vers le niveau habituel : l'écart de l'année (sur l'échelle z) au niveau habituel se
  résorbe d'un facteur φ par an, z(t+h) = niveau + φ^h × écart ; φ est choisi sur les plis de sélection ;
- combinaison du niveau habituel et de l'elastic net (moyenne sur l'échelle z).

Échelle : tous les modèles travaillent sur z = logit(taux / 100) ; prévisions et intervalles sont
dénormalisés, donc toujours entre 0 et 100 %. Les mesures de qualité sont calculées en points de
taux, après dénormalisation.

Les modèles appris prédisent l'écart (sur l'échelle z) au niveau habituel de la province, diminué
du choc commun à toutes les provinces l'année de la cible (crise nationale).

Sélection des variables et réglages, sans fuite d'information : dans chaque pli, les variables
sont classées par importance par permutation, mesurée sur la dernière année de l'apprentissage
d'un LightGBM appris sur les années précédentes ; chaque modèle garde ses k premières. Le nombre
k, les pénalités, les paramètres de LightGBM et le κ du niveau rétréci sont choisis sur les plis
de sélection. Le modèle final garde les variables retenues dans au moins la moitié des plis.

Choix du modèle : le niveau habituel est le modèle à battre. Un autre modèle n'est retenu que s'il
réduit l'erreur moyenne des plis de sélection d'au moins 3 % et fait mieux sur au moins deux plis
sur trois : un écart plus faible s'explique par le hasard des plis. À défaut, un modèle qui suit la
situation de l'année (retour amorti, combinaison) est préféré au niveau habituel s'il est aussi précis
sur les plis de sélection, à 1 % près : à précision égale, la prévision exploite l'information récente.
Le test final ne sert jamais au choix.

Intervalle à 80 % : prédiction conforme sur l'échelle z (quantiles conformalisés pour LightGBM,
écart absolu sinon), puis dénormalisation ; couverture vérifiée sur le test final.
"""

from __future__ import annotations

import math
from collections import Counter

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.linear_model import ElasticNet, Ridge

from . import elimination as EL
from . import preparation as P

NIVEAU = 0.80
GRILLE_K = [5, 10, 15, None]
GRILLE_ELASTIC = [0.003, 0.01, 0.03, 0.1, 0.3]
GRILLE_RIDGE = [10.0, 30.0, 100.0, 300.0, 1000.0]
COMMUN_LGB = dict(learning_rate=0.03, subsample=0.8, subsample_freq=1, colsample_bytree=0.7, verbose=-1,
                  random_state=42, n_jobs=1)
GRILLE_LGB = [
    dict(num_leaves=4, max_depth=2, min_child_samples=20, n_estimators=300, reg_lambda=2.0),
    dict(num_leaves=7, max_depth=3, min_child_samples=15, n_estimators=400, reg_lambda=2.0),
    dict(num_leaves=7, max_depth=3, min_child_samples=30, n_estimators=200, reg_lambda=5.0),
]
GRILLE_PHI = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
MODELES = ["reference_annee_precedente", "reference_niveau_habituel", "reference_niveau_retreci", "elastic_net",
           "ridge_effet_province", "lightgbm", "lightgbm_elimination", "moyenne_elastic_lightgbm",
           "retour_amorti", "combinaison_niveau_elastic"]
REFERENCE = "reference_niveau_habituel"
GAIN_MINIMAL = 0.03
INFORMATIFS = ["retour_amorti", "combinaison_niveau_elastic"]
ECART_EQUIVALENT = 0.01
SEUIL_HAUSSE = 2.0


def _relative(t: pd.DataFrame) -> pd.Series:
    """Écart au niveau habituel sur l'échelle z, diminué du choc commun de l'année de la cible."""
    e = t["z"] - t["base_z"]
    return e - e.groupby(t["annee_cible"]).transform("mean")


def _lgb(params: dict, objectif: str = "quantile", alpha: float = 0.5):
    return lgb.LGBMRegressor(objective=objectif, alpha=alpha, **COMMUN_LGB, **params)


def classement(train: pd.DataFrame, variables: list[str]) -> list[str]:
    """Variables par importance par permutation (dernière année de l'apprentissage, modèle appris avant)."""
    derniere = train["annee_cible"].max()
    a, v = train[train["annee_cible"] < derniere], train[train["annee_cible"] == derniere]
    m = _lgb(GRILLE_LGB[0]).fit(a[variables].astype(float), _relative(a), sample_weight=a["poids"])
    r = permutation_importance(m, v[variables].astype(float), _relative(v), scoring="neg_mean_absolute_error",
                               n_repeats=5, random_state=42)
    return [variables[i] for i in np.argsort(-r.importances_mean)]


def _choisies(rang: list[str], liste: list[str], k) -> list[str]:
    retenues = [v for v in rang if v in liste]
    return retenues if k is None else retenues[:k]


def retour_amorti(test, phi: float, horizon: int) -> np.ndarray:
    """Niveau habituel plus l'écart de l'année, amorti d'un facteur φ par an (écart nul après une rupture)."""
    ecart = P.normaliser(test[P.CIBLE].clip(lower=0)) - test["base_z"]
    ecart = ecart.where((test["rupture_annee_precedente"] == 0) & test[P.CIBLE].notna(), 0.0)
    return (test["base_z"] + phi ** horizon * ecart).values


def elastic(train, test, variables, alpha):
    xa, xt = P.matrice_lineaire(train, test, variables)
    m = ElasticNet(alpha=alpha, l1_ratio=0.5, max_iter=50000, random_state=42)
    m.fit(xa, _relative(train), sample_weight=train["poids"])
    return m.predict(xt) + test["base_z"].values


def ridge_province(train, test, variables, alpha):
    xa, xt = P.matrice_lineaire(train, test, variables)
    for p in sorted(set(train["province_pcode"])):
        xa[f"province_{p}"] = (train["province_pcode"] == p).astype(float)
        xt[f"province_{p}"] = (test["province_pcode"] == p).astype(float)
    m = Ridge(alpha=alpha).fit(xa, _relative(train), sample_weight=train["poids"])
    return m.predict(xt) + test["base_z"].values


def lightgbm_median(train, test, variables, params):
    m = _lgb(params).fit(train[variables].astype(float), _relative(train), sample_weight=train["poids"])
    return m.predict(test[variables].astype(float)) + test["base_z"].values


def lightgbm_bornes(train, test, variables, params):
    bornes = []
    for q in (0.10, 0.90):
        m = _lgb(params, alpha=q).fit(train[variables].astype(float), _relative(train), sample_weight=train["poids"])
        bornes.append(m.predict(test[variables].astype(float)) + test["base_z"].values)
    return np.minimum(*bornes), np.maximum(*bornes)


def variables_par_modele(rang, lineaire, arbres, reglages) -> dict[str, list[str]]:
    return {"elastic_net": _choisies(rang, lineaire, reglages["k_elastic"]),
            "ridge_effet_province": _choisies(rang, lineaire, reglages["k_ridge"]),
            "lightgbm": _choisies(rang, arbres, reglages["k_lightgbm"])}


def predire(train, test, choix: dict[str, list[str]], reglages, horizon: int = 1) -> dict[str, np.ndarray]:
    """Prévisions sur l'échelle z de chaque modèle (et bornes quantiles de LightGBM)."""
    params = GRILLE_LGB[reglages["lightgbm"]]
    p = {"reference_annee_precedente": P.normaliser(test[P.CIBLE]),
         "reference_niveau_habituel": test["base_z"].values,
         "reference_niveau_retreci": P.normaliser(test[f"niveau_retreci_{reglages['kappa']:g}"])}
    p["elastic_net"] = elastic(train, test, choix["elastic_net"], reglages["alpha_elastic"])
    p["ridge_effet_province"] = ridge_province(train, test, choix["ridge_effet_province"], reglages["alpha_ridge"])
    p["lightgbm"] = lightgbm_median(train, test, choix["lightgbm"], params)
    p["lightgbm_bas"], p["lightgbm_haut"] = lightgbm_bornes(train, test, choix["lightgbm"], params)
    p["lightgbm_elimination"] = lightgbm_median(train, test, choix["lightgbm_elimination"], params)
    p["moyenne_elastic_lightgbm"] = (p["elastic_net"] + p["lightgbm"]) / 2
    p["retour_amorti"] = retour_amorti(test, reglages["phi"], horizon)
    p["combinaison_niveau_elastic"] = (p["reference_niveau_habituel"] + p["elastic_net"]) / 2
    return p


def _erreur(test, z) -> float:
    return float(np.mean(np.abs(test["y"].values - P.denormaliser(z))))


def choisir_reglages(t, lineaire, arbres, nom) -> tuple[dict, dict]:
    """Réglages choisis sur les plis de sélection (erreur moyenne en points) ; classements par pli."""
    erreurs = {}
    rangs = {}

    def noter(cle, valeur):
        erreurs.setdefault(cle, []).append(valeur)

    for annee, train, test in P.plis(t, P.PLIS[nom], 1):
        rang = rangs[annee] = classement(train, arbres)
        for kappa in P.GRILLE_KAPPA:
            noter(("kappa", kappa), _erreur(test, P.normaliser(test[f"niveau_retreci_{kappa:g}"])))
        for phi in GRILLE_PHI:
            noter(("phi", phi), _erreur(test, retour_amorti(test, phi, 1)))
        for k in GRILLE_K:
            for a in GRILLE_ELASTIC:
                noter(("elastic", a, k), _erreur(test, elastic(train, test, _choisies(rang, lineaire, k), a)))
            for a in GRILLE_RIDGE:
                noter(("ridge", a, k), _erreur(test, ridge_province(train, test, _choisies(rang, lineaire, k), a)))
            for i, params in enumerate(GRILLE_LGB):
                noter(("lgb", i, k), _erreur(test, lightgbm_median(train, test, _choisies(rang, arbres, k), params)))
    moyenne = {cle: np.mean(v) for cle, v in erreurs.items()}
    meilleur = lambda famille: min((c for c in moyenne if c[0] == famille), key=moyenne.get)  # noqa: E731
    _, kappa = meilleur("kappa")
    _, phi = meilleur("phi")
    _, alpha_e, k_e = meilleur("elastic")
    _, alpha_r, k_r = meilleur("ridge")
    _, i_lgb, k_l = meilleur("lgb")
    reglages = {"kappa": kappa, "phi": phi, "alpha_elastic": alpha_e, "k_elastic": k_e, "alpha_ridge": alpha_r, "k_ridge": k_r,
                "lightgbm": i_lgb, "k_lightgbm": k_l}
    grille = pd.DataFrame([{"famille": c[0], "parametre": c[1], "k": c[2] if len(c) > 2 else None,
                            "erreur_moyenne_plis_selection": round(v, 4)} for c, v in moyenne.items()])
    return reglages, {"rangs": rangs, "grille": grille}


def evaluer(t, lineaire, arbres, reglages, entite, nom, horizon):
    """Prévisions hors échantillon de chaque pli et du test final, mesures et variables choisies."""
    lignes, previsions, choix_plis, courbes = [], [], [], []
    for annee, train, test in P.plis(t, P.PLIS[nom] + [P.TEST_FINAL[nom]], horizon):
        choix = variables_par_modele(classement(train, arbres), lineaire, arbres, reglages)
        choix["lightgbm_elimination"], etapes = EL.variables_prevision(
            train, arbres, GRILLE_LGB[reglages["lightgbm"]], _relative, _lgb)
        courbes.append(pd.DataFrame([{"horizon": horizon, "annee_cible": annee, "nombre_de_variables": len(v),
                                      "erreur_validation_interne": round(e, 4)} for v, e in etapes]))
        choix_plis.append(choix)
        p = predire(train, test, choix, reglages, horizon)
        role = "test final" if annee == P.TEST_FINAL[nom] else "sélection"
        for m in MODELES:
            lignes.append({"horizon": horizon, "annee_cible": annee, "role": role, "modele": m,
                           "lignes_apprentissage": len(train), "lignes_test": len(test),
                           **P.mesures(test["y"].values, P.denormaliser(p[m]))})
        previsions.append(test[entite + ["annee_scolaire", "annee_cible", "y", "z"]].assign(
            role=role, **{m: p[m] for m in MODELES + ["lightgbm_bas", "lightgbm_haut"]}))
    if not lignes:
        return pd.DataFrame(), pd.DataFrame(), [], pd.DataFrame()
    return pd.DataFrame(lignes), pd.concat(previsions, ignore_index=True), choix_plis, pd.concat(courbes)


def variables_stables(choix_plis: list[dict], modele: str) -> tuple[list[str], pd.DataFrame]:
    """Variables retenues dans au moins la moitié des plis, par fréquence décroissante."""
    compte = Counter(v for c in choix_plis for v in c[modele])
    n = len(choix_plis)
    frequence = pd.DataFrame([{"modele": modele, "variable": v, "part_des_plis": round(c / n, 2)}
                              for v, c in compte.most_common()])
    stables = [v for v, c in compte.most_common() if c / n >= 0.5]
    return stables, frequence


def synthese(evaluation: pd.DataFrame) -> pd.DataFrame:
    colonnes = ["erreur_absolue_moyenne", "correlation_rang", "rappel_quintile_le_plus_a_risque"]
    return evaluation.groupby(["horizon", "role", "modele"])[colonnes].mean().round(3).reset_index()


def choisir_modele(evaluation: pd.DataFrame) -> str:
    """Le niveau habituel est le modèle à battre (analyse exploratoire). Un autre modèle n'est retenu que s'il
    réduit l'erreur moyenne des plis de sélection d'au moins 3 % et fait mieux sur au moins deux plis sur trois ;
    parmi ceux qui y parviennent, celui de plus petite erreur."""
    s = evaluation[evaluation["role"] == "sélection"].pivot_table(index="annee_cible", columns="modele",
                                                                  values="erreur_absolue_moyenne")
    reference = s[REFERENCE]
    gain = 1 - s.mean() / reference.mean()
    plis_gagnes = (s.lt(reference, axis=0)).mean()
    eligibles = [m for m in s.columns if m != REFERENCE and gain[m] >= GAIN_MINIMAL and plis_gagnes[m] >= 2 / 3]
    if eligibles:
        return min(eligibles, key=lambda m: s[m].mean())
    # À précision équivalente (à 1 % près), préférer un modèle qui suit la situation de l'année.
    equivalents = [m for m in INFORMATIFS if m in s.columns and gain[m] >= -ECART_EQUIVALENT]
    return min(equivalents, key=lambda m: s[m].mean()) if equivalents else REFERENCE


def marge_conforme(prev: pd.DataFrame, modele: str) -> float:
    """Marge (échelle z) de l'intervalle à 80 % : quantile conformalisé des scores de non-conformité."""
    if modele == "lightgbm":
        score = np.maximum(prev["lightgbm_bas"] - prev["z"], prev["z"] - prev["lightgbm_haut"])
    else:
        score = (prev["z"] - prev[modele]).abs()
    n = len(score)
    return float(np.quantile(score, min(1.0, math.ceil((n + 1) * NIVEAU) / n)))


def intervalle(p: dict, modele: str, marge: float) -> tuple[np.ndarray, np.ndarray]:
    """Bornes dénormalisées (taux en %)."""
    if modele == "lightgbm":
        return P.denormaliser(np.asarray(p["lightgbm_bas"]) - marge), P.denormaliser(np.asarray(p["lightgbm_haut"]) + marge)
    z = np.asarray(p[modele])
    return P.denormaliser(z - marge), P.denormaliser(z + marge)


def couverture(prev_test: pd.DataFrame, modele: str, marge: float, horizon: int) -> dict:
    bas, haut = intervalle(prev_test, modele, marge)
    dedans = (prev_test["y"] >= bas) & (prev_test["y"] <= haut)
    return {"horizon": horizon, "modele": modele, "marge_conforme_logit": round(marge, 3),
            "couverture_test_final": round(float(dedans.mean()), 3),
            "largeur_moyenne_points": round(float(np.mean(haut - bas)), 3), "lignes": len(prev_test)}


def prevoir(d, t, nom, choix, reglages, modele, marge, horizon, annees_x):
    """Modèle retenu, appris sur toutes les cibles apprenables, appliqué aux variables des années ``annees_x``."""
    train = t[t["apprenable"]]
    x = d[d["annee_scolaire"].isin(annees_x)].copy()
    p = predire(train, x, choix, reglages, horizon)
    taux = P.denormaliser(p[modele])
    bas, haut = intervalle(p, modele, marge)
    seuils = train["y"].quantile([0.5, 0.8]).values
    sortie = x[["province_pcode", "province_nom", "region_nom", "province_ancienne_nom", "methode_passage"]
               + (["sexe"] if nom == "sexe" else []) + ["annee_scolaire", P.CIBLE]].rename(
        columns={"annee_scolaire": "annee_des_variables", P.CIBLE: "taux_abandon_annee_des_variables"})
    sortie["province_scindee"] = sortie.pop("methode_passage").str.startswith("province scindée")
    sortie["annee_prevue"] = x["annee_scolaire"].map(lambda a: P.annee_plus(a, horizon))
    sortie["horizon"] = horizon
    sortie["modele"] = modele
    sortie["taux_abandon_prevu"] = np.round(taux, 2)
    sortie["borne_basse_80"] = np.round(bas, 2)
    sortie["borne_haute_80"] = np.round(haut, 2)
    sortie["classe_de_risque"] = np.select([taux >= seuils[1], taux >= seuils[0]], ["élevé", "moyen"], "faible")
    # Prévision nettement au-dessus du taux de l'année des variables (retour vers un niveau habituel plus élevé).
    sortie["prevision_au_dessus_du_taux_actuel"] = (taux - x[P.CIBLE].clip(lower=0).values) > SEUIL_HAUSSE
    return sortie.reset_index(drop=True), seuils
