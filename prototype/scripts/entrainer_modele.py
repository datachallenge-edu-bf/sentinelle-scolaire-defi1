"""Entraîne le score élève (régression logistique explicable) sur les données FICTIVES,
calcule pour chaque élève son risque, ses trois raisons principales et un levier contrefactuel.

Sorties : data/eleves_scores.csv, data/modele_metriques.json
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
el = pd.read_csv(DATA / "eleves_fictifs.csv")
reg = pd.read_csv(DATA / "indicateurs_regions_2024_2025.csv").set_index("region")

# ---------- variables explicatives (signaux scolaires + contexte) ----------
X = pd.DataFrame({
    "absences_t2": el["absences_t2"],
    "hausse_absences": (el["absences_t2"] - el["absences_t1"]).clip(lower=0),
    "baisse_moyenne": (el["moyenne_t1"] - el["moyenne_t2"]).clip(lower=0),
    "redoublant": el["redoublant"].astype(int),
    "retard_age": el["retard_age"],
    "deplace": el["deplace"].astype(int),
    "distance_km": el["distance_km"],
    "sans_cantine": (~el["cantine"]).astype(int),
    "fille_fin_cycle": ((el["sexe"] == "F") & el["classe"].isin(["CM1", "CM2"])).astype(int),
    "risque_territoire": 1 - el["region"].map(reg["achevement_total"]) / 100,
})
LIBELLES = {
    "absences_t2": "absences élevées au 2e trimestre",
    "hausse_absences": "absences en hausse depuis le 1er trimestre",
    "baisse_moyenne": "moyenne en baisse",
    "redoublant": "redoublement",
    "retard_age": "retard d’âge",
    "deplace": "élève déplacé",
    "distance_km": "école éloignée du domicile",
    "sans_cantine": "pas de cantine dans l’école",
    "fille_fin_cycle": "fille en fin de cycle",
    "risque_territoire": "contexte territorial défavorable",
}
y = el["abandon"].astype(int)

# ---------- entraînement, séparation par école (pas de fuite entre écoles) ----------
gss = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=42)
tr, te = next(gss.split(X, y, groups=el["ecole_id"]))
sc = StandardScaler().fit(X.iloc[tr])
clf = LogisticRegression(max_iter=2000).fit(sc.transform(X.iloc[tr]), y.iloc[tr])
p_te = clf.predict_proba(sc.transform(X.iloc[te]))[:, 1]

def rappel_top(p, yy, part=0.2):
    k = int(np.ceil(part * len(p)))
    idx = np.argsort(-p)[:k]
    return yy.iloc[idx].sum() / yy.sum()

# référence naïve : classer uniquement selon le risque du territoire
naif = X.iloc[te]["risque_territoire"].values + 1e-6 * np.random.default_rng(0).random(len(te))
metriques = {
    "donnees": "fictives",
    "n_eleves_test": int(len(te)),
    "prevalence_test": round(float(y.iloc[te].mean()), 3),
    "roc_auc": round(float(roc_auc_score(y.iloc[te], p_te)), 3),
    "pr_auc": round(float(average_precision_score(y.iloc[te], p_te)), 3),
    "rappel_top20": round(float(rappel_top(p_te, y.iloc[te])), 3),
    "rappel_top20_reference_territoire": round(float(rappel_top(naif, y.iloc[te])), 3),
}
(DATA / "modele_metriques.json").write_text(json.dumps(metriques, indent=2, ensure_ascii=False))
print(metriques)

# ---------- scores, raisons et leviers pour tous les élèves ----------
Z = sc.transform(X)
proba = clf.predict_proba(Z)[:, 1]
contrib = Z * clf.coef_[0]  # contribution de chaque variable au logit (écart à l'élève moyen)
noms = list(X.columns)

def levier(i):
    """Explication contrefactuelle : effet d'un retour sous 9 absences par trimestre (3 par mois)."""
    x = X.iloc[[i]].copy()
    if x["absences_t2"].iloc[0] <= 9:
        return "", np.nan
    x["absences_t2"] = 9
    x["hausse_absences"] = max(0, 9 - el["absences_t1"].iloc[i])
    return "revenir sous 3 absences par mois", float(clf.predict_proba(sc.transform(x))[:, 1][0])

rows = []
for i in range(len(el)):
    ordre = np.argsort(-contrib[i])
    raisons = [LIBELLES[noms[j]] for j in ordre[:3] if contrib[i, j] > 0]
    lev, p_lev = levier(i)
    rows.append({"risque": round(float(proba[i]), 3), "raison_1": raisons[0] if len(raisons) > 0 else "",
                 "raison_2": raisons[1] if len(raisons) > 1 else "", "raison_3": raisons[2] if len(raisons) > 2 else "",
                 "levier": lev, "risque_apres_levier": round(p_lev, 3) if lev else np.nan})
out = pd.concat([el, pd.DataFrame(rows)], axis=1)
out["niveau"] = pd.cut(out["risque"], [-1, 0.15, 0.35, 2], labels=["faible", "moyen", "élevé"])
out.to_csv(DATA / "eleves_scores.csv", index=False)
coefs = pd.Series(clf.coef_[0], index=[LIBELLES[n] for n in noms]).sort_values(ascending=False)
print(coefs.round(2).to_string())
print(out.loc[out["vitrine"]].head(1)[["prenom", "classe", "province", "risque", "raison_1", "raison_2", "raison_3", "risque_apres_levier"]].to_string())
