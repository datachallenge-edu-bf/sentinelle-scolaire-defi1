"""Brique 3 : alerte de rupture de scolarisation.

Une rupture est une variation des effectifs du primaire de la province de plus de 30 % entre t et
t+1 (fermetures d'écoles, départs d'élèves). Le score est donné par une régression logistique
pénalisée, aux classes équilibrées, sur des signaux connus à la date t : évolution et baisse des
effectifs, rupture l'année précédente, ruptures passées, taux d'abandon de l'année, abandons pour
l'orpaillage, jeunes hors de l'école. Avec peu de ruptures passées, le score est présenté en
classes (faible, moyen, élevé) plutôt qu'en probabilité.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from . import preparation as P
from .libelles import libelle

VARIABLES = ["evolution_eleves_primaire", "baisse_effectifs", "rupture_annee_precedente", "ruptures_passees",
             P.CIBLE, "abandons_primaire_orpaillage_pour_1000_region", "hors_ecole_16_18_province"]
SEUILS = (0.3, 0.6)


def _ajuster(train, test):
    xa, xt = P.matrice_lineaire(train, test, VARIABLES)
    m = LogisticRegression(C=0.5, class_weight="balanced", max_iter=5000)
    m.fit(xa, train["rupture"])
    return m.predict_proba(xt)[:, 1], m, list(xt.columns)


def executer(d: pd.DataFrame, t: pd.DataFrame) -> dict[str, pd.DataFrame]:
    lignes = t[t["y"].notna() & t["y_observee"]].copy()
    lignes["rupture"] = lignes["rupture_cible"].astype(int)
    evaluation = []
    for annee in P.PLIS["ensemble"] + [P.TEST_FINAL["ensemble"]]:
        test = lignes[lignes["annee_cible"] == annee]
        train = lignes[lignes["annee_cible"] <= P.annee_plus(annee, -1)]
        ligne = {"annee_cible": annee, "role": "test final" if annee == P.TEST_FINAL["ensemble"] else "sélection",
                 "provinces": len(test), "ruptures": int(test["rupture"].sum())}
        if test["rupture"].nunique() == 2 and train["rupture"].sum() > 0:
            score, _, _ = _ajuster(train, test)
            quart = test["rupture"].values[np.argsort(-score)[:max(1, len(test) // 4)]]
            ligne.update({"auc": round(roc_auc_score(test["rupture"], score), 3),
                          "ruptures_dans_le_quart_le_plus_a_risque": int(quart.sum())})
        evaluation.append(ligne)
    x = d[d["annee_scolaire"] == P.DERNIERE_ANNEE].copy()
    score, m, colonnes = _ajuster(lignes, x)
    sortie = x[["province_pcode", "province_nom", "region_nom"]].copy()
    sortie["annee_prevue"] = P.annee_plus(P.DERNIERE_ANNEE, 1)
    sortie["score_rupture"] = np.round(score, 3)
    sortie["risque_de_rupture"] = np.select([score >= SEUILS[1], score >= SEUILS[0]], ["élevé", "moyen"], "faible")
    coefficients = pd.DataFrame({"variable": colonnes, "libelle": [libelle(c.replace("__manquante", "")) for c in colonnes],
                                 "coefficient_standardise": np.round(m.coef_[0], 3)}).sort_values(
        "coefficient_standardise", key=abs, ascending=False)
    return {"alerte_rupture": sortie.sort_values("score_rupture", ascending=False).reset_index(drop=True),
            "evaluation_alerte_rupture": pd.DataFrame(evaluation), "coefficients_alerte_rupture": coefficients}
