"""Prépare les données du prototype web (data.json) à partir de ../data."""
import json, math
from pathlib import Path
import pandas as pd
from shapely.geometry import shape, mapping

D = Path(__file__).resolve().parent.parent / "data"
OUT = Path(__file__).resolve().parent

reg = pd.read_csv(D / "indicateurs_regions_2024_2025.csv")
ferm = pd.read_csv(D / "fermetures_ecoles.csv")
eco = pd.read_csv(D / "ecoles_fictives.csv")
el = pd.read_csv(D / "eleves_scores.csv", keep_default_na=False)
met = json.loads((D / "modele_metriques.json").read_text())
geo = json.loads((D / "provinces_bfa_45.geojson").read_text(encoding="utf-8"))

# ---------- projection SVG
LAT0 = 12.2
kx = math.cos(math.radians(LAT0))
feats = []
xs, ys = [], []
for f in geo["features"]:
    g = shape(f["geometry"]).simplify(0.012, preserve_topology=True)
    feats.append((f["properties"], g))
    for poly in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
        for x, y in poly.exterior.coords:
            xs.append(x * kx); ys.append(y)
minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
W = 600
S = W / (maxx - minx)
H = round((maxy - miny) * S)

def path(g):
    out = []
    for poly in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
        pts = [((x * kx - minx) * S, (maxy - y) * S) for x, y in poly.exterior.coords]
        out.append("M" + "L".join(f"{a:.1f},{b:.1f}" for a, b in pts) + "Z")
    return "".join(out)

def centroid(g):
    c = g.representative_point()
    return [round((c.x * kx - minx) * S, 1), round((maxy - c.y) * S, 1)]

# ---------- risque simulé par province / région (données fictives)
el["eleve_haut"] = el["niveau"] == "élevé"
prov_r = el.groupby("province").agg(risque=("risque", "mean"), n=("eleve_id", "size"),
                                     haut=("eleve_haut", "sum")).reset_index()
reg_r = el.groupby("region").agg(risque=("risque", "mean"), haut=("eleve_haut", "sum"), n=("eleve_id", "size")).reset_index()

provinces = []
for p, g in feats:
    r = prov_r.set_index("province").loc[p["province"]]
    provinces.append({"province": p["province"], "region": p["region"], "d": path(g), "c": centroid(g),
                      "risque": round(float(r["risque"]) * 100, 1), "haut": int(r["haut"]), "n": int(r["n"])})

# facteurs associés par région : part des élèves à risque élevé concernés par chaque raison
raisons = ["absences élevées au 2e trimestre", "absences en hausse depuis le 1er trimestre", "moyenne en baisse",
           "école éloignée du domicile", "pas de cantine dans l’école", "élève déplacé", "fille en fin de cycle",
           "retard d’âge", "redoublement", "contexte territorial défavorable"]
def facteurs(sub):
    h = sub[sub["niveau"].isin(["élevé", "moyen"])]
    if len(h) == 0:
        return []
    res = []
    for r_ in raisons:
        part = ((h["raison_1"] == r_) | (h["raison_2"] == r_) | (h["raison_3"] == r_)).mean()
        res.append([r_, round(part * 100)])
    return sorted(res, key=lambda t: -t[1])[:4]

regions = []
for _, r in reg.iterrows():
    rr = reg_r.set_index("region").loc[r["region"]]
    sub = el[el["region"] == r["region"]]
    regions.append({"region": r["region"], "ach": r["achevement_total"], "ach_g": r["achevement_garcons"],
                    "ach_f": r["achevement_filles"], "tbs": r["tbs_total"],
                    "risque": round(float(rr["risque"]) * 100, 1), "haut": int(rr["haut"]), "n": int(rr["n"]),
                    "facteurs": facteurs(sub)})

# écoles : risque moyen et nombre d’élèves à risque élevé
ec = el.groupby("ecole_id").agg(risque=("risque", "mean"), haut=("eleve_haut", "sum"), n=("eleve_id", "size")).reset_index()
ec = ec.merge(eco[["ecole_id", "nom", "province", "region", "cantine", "part_deplaces"]], on="ecole_id")
ecoles = [{"id": r.ecole_id, "nom": r.nom, "province": r.province, "region": r.region, "risque": round(r.risque * 100, 1),
           "haut": int(r.haut), "n": int(r.n), "cantine": bool(r.cantine), "dep": round(r.part_deplaces * 100)}
          for r in ec.itertuples()]

# élèves : seulement les colonnes utiles (pour les écoles, on garde tout l’effectif)
cols = ["eleve_id", "prenom", "sexe", "ecole_id", "province", "region", "classe", "age", "absences_t1", "absences_t2",
        "moyenne_t1", "moyenne_t2", "deplace", "distance_km", "cantine", "risque", "raison_1", "raison_2", "raison_3",
        "levier", "risque_apres_levier", "niveau", "vitrine"]
keep = set(ec.sort_values("risque", ascending=False).groupby("region").head(3)["ecole_id"]) | set(el.loc[el["vitrine"], "ecole_id"])
ecoles = [e for e in ecoles if e["id"] in keep]
eleves = el.loc[el["ecole_id"].isin(keep), cols].copy()
eleves["risque"] = (eleves["risque"] * 100).round(0).astype(int)
eleves["risque_apres_levier"] = pd.to_numeric(eleves["risque_apres_levier"], errors="coerce").mul(100).round(0)
eleves = eleves.astype(object).where(eleves.notna(), None)
for k in ("deplace", "cantine", "vitrine"):
    eleves[k] = eleves[k].astype(str) == "True"
recs = {"cols": cols, "rows": eleves.values.tolist()}

data = {
    "map": {"w": W, "h": H, "provinces": provinces},
    "regions": regions,
    "fermetures": ferm[["date", "etablissements_fermes", "source"]].values.tolist(),
    "ecoles": ecoles,
    "eleves": recs,
    "metriques": met,
    "kpi": {"ach_nat": 51.6, "fermes": 6149, "reg_sous40": int((reg["achevement_total"] < 40).sum()),
            "suivis": int(len(el)), "haut": int(el["eleve_haut"].sum())},
}
(OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("ok", W, H, len(provinces), len(recs["rows"]), round((OUT / "data.json").stat().st_size / 1e6, 2), "Mo")
print(prov_r["risque"].describe())
print(reg_r.sort_values("risque"))
