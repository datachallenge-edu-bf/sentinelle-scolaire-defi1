"""Génère des écoles et des élèves FICTIFS pour illustrer les vues école et élève du prototype.

Aucun élève réel. Les paramètres sont choisis pour être vraisemblables :
- le niveau de risque régional est calé sur le taux d'achèvement réel 2024-2025 (DGESS, 2025) ;
- les effets des signaux scolaires (absences, notes, redoublement) suivent la logique « ABC ».
"""
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd

RNG = np.random.default_rng(2026)
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

prov = gpd.read_file(DATA / "provinces_bfa_45.geojson")
ind = pd.read_csv(DATA / "indicateurs_regions_2024_2025.csv").set_index("region")

# Régions les plus exposées à la crise sécuritaire (UNICEF, 2023 ; DGESS, 2025)
INSECURITE = {"Sahel": 0.8, "Est": 0.8, "Centre-Nord": 0.6, "Boucle du Mouhoun": 0.6, "Nord": 0.5,
              "Centre-Est": 0.3, "Cascades": 0.2, "Sud-Ouest": 0.2, "Hauts-Bassins": 0.15,
              "Plateau-Central": 0.15, "Centre-Ouest": 0.1, "Centre-Sud": 0.1, "Centre": 0.0}

PRENOMS_F = ["Aïcha", "Aminata", "Fatimata", "Mariam", "Rasmata", "Safiatou", "Salimata", "Haoua", "Assita", "Bibata",
             "Alimata", "Zalissa", "Pauline", "Odette", "Kadidia", "Sanata", "Ramata", "Djeneba", "Habibou", "Ines"]
PRENOMS_G = ["Ibrahim", "Moussa", "Salif", "Issouf", "Boukary", "Adama", "Ousmane", "Souleymane", "Abdoulaye", "Hamidou",
             "Seydou", "Idrissa", "Arouna", "Mahamadi", "Yacouba", "Lassané", "Daouda", "Karim", "Paul", "Noufou"]
CLASSES = ["CP1", "CP2", "CE1", "CE2", "CM1", "CM2"]
AGE_NORMAL = dict(zip(CLASSES, [6, 7, 8, 9, 10, 11]))


def point_dans(geom):
    minx, miny, maxx, maxy = geom.bounds
    while True:
        x, y = RNG.uniform(minx, maxx), RNG.uniform(miny, maxy)
        from shapely.geometry import Point
        if geom.contains(Point(x, y)):
            return x, y


# ---------- écoles ----------
ecoles = []
for _, p in prov.iterrows():
    reg = p["region"]
    for k in range(4):
        lon, lat = point_dans(p.geometry)
        urbain = RNG.random() < (0.8 if p["province"] == "Kadiogo" else 0.15)
        ecoles.append({
            "ecole_id": f"E{len(ecoles)+1:03d}",
            "nom": f"École {'A' if urbain else 'B'}{len(ecoles)+1:03d} de {p['province']}",
            "province": p["province"], "region": reg,
            "milieu": "urbain" if urbain else "rural",
            "cantine": bool(RNG.random() < (0.45 if urbain else 0.7)),
            "distance_moy_km": round(float(RNG.gamma(2, 0.6 if urbain else 1.6)), 1),
            "part_deplaces": round(float(np.clip(RNG.beta(2, 8) * (0.3 + 1.5 * INSECURITE[reg]), 0, 0.8)), 2),
            "lat": round(lat, 4), "lon": round(lon, 4),
        })
ecoles = pd.DataFrame(ecoles)

# ---------- élèves ----------
eleves = []
for _, e in ecoles.iterrows():
    base = -5.8 + 3.2 * (1 - ind.loc[e["region"], "achevement_total"] / 100)  # calage régional
    for j in range(int(RNG.integers(45, 75))):
        fille = RNG.random() < 0.49
        classe = CLASSES[int(RNG.integers(0, 6))]
        retard = int(RNG.choice([0, 0, 0, 1, 1, 2, 3], p=[.3, .2, .15, .15, .1, .06, .04]))
        age = AGE_NORMAL[classe] + retard
        redoublant = bool(RNG.random() < 0.12 + 0.05 * retard)
        deplace = bool(RNG.random() < e["part_deplaces"])
        distance = round(float(max(0.2, RNG.normal(e["distance_moy_km"], 1.0))), 1)
        abs_t1 = int(RNG.poisson(2 + 3 * deplace + 0.4 * distance))
        choc = RNG.random() < 0.18  # dégradation au 2e trimestre
        abs_t2 = int(abs_t1 + RNG.poisson(1) + (RNG.integers(4, 10) if choc else 0))
        moy_t1 = float(np.clip(RNG.normal(5.8 - 0.4 * retard, 1.3), 1, 9.8))
        moy_t2 = float(np.clip(moy_t1 - (RNG.uniform(1.5, 3.5) if choc else RNG.normal(0, 0.6)), 0.5, 9.9))
        logit = (base + 0.16 * abs_t2 + 0.45 * max(0, moy_t1 - moy_t2) + 0.6 * redoublant + 0.3 * retard
                 + 0.55 * deplace + 0.07 * distance - 0.45 * e["cantine"]
                 + (0.35 if (fille and classe in ("CM1", "CM2")) else 0))
        p = 1 / (1 + np.exp(-logit))
        prenom = RNG.choice(PRENOMS_F if fille else PRENOMS_G)
        eleves.append({
            "eleve_id": f"{e['ecole_id']}-{j+1:03d}", "prenom": prenom, "sexe": "F" if fille else "G",
            "ecole_id": e["ecole_id"], "province": e["province"], "region": e["region"],
            "classe": classe, "age": age, "retard_age": retard, "redoublant": redoublant, "deplace": deplace,
            "distance_km": distance, "cantine": e["cantine"],
            "absences_t1": abs_t1, "absences_t2": abs_t2,
            "moyenne_t1": round(moy_t1, 1), "moyenne_t2": round(moy_t2, 1),
            "abandon": bool(RNG.random() < p),
        })
eleves = pd.DataFrame(eleves)

# Élève vitrine de la note d'intention (cas fictif « Awa »)
i = eleves.index[(eleves["province"] == "Sanmatenga") & (eleves["sexe"] == "F")][0]
eleves.loc[i, ["prenom", "classe", "age", "retard_age", "redoublant", "deplace",
               "absences_t1", "absences_t2", "moyenne_t1", "moyenne_t2"]] = ["Awa", "CM2", 12, 1, False, False, 3, 12, 6.1, 3.1]
eleves["vitrine"] = False
eleves.loc[i, "vitrine"] = True
ecoles.loc[ecoles["ecole_id"] == eleves.loc[i, "ecole_id"], "milieu"] = "rural"

ecoles["donnees"] = "fictives"
eleves["donnees"] = "fictives"
ecoles.to_csv(DATA / "ecoles_fictives.csv", index=False)
eleves.to_csv(DATA / "eleves_fictifs.csv", index=False)
print(f"{len(ecoles)} écoles, {len(eleves)} élèves, taux d'abandon simulé : {eleves['abandon'].mean():.1%}")
print(eleves.groupby("region")["abandon"].mean().sort_values().round(3).to_string())
