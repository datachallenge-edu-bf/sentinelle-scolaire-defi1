"""API de Sentinelle Scolaire : cartes, fiches et alertes du risque de décrochage au primaire.

Lancement (depuis ``defi1_sentinelle/application/api``) : ``uvicorn main:app --port 8000``.
Documentation interactive : http://localhost:8000/docs
"""

from __future__ import annotations

import json
import os
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from donnees import (ANNEE_PREVUE, ANNEES_PROJETEES, DONNEES_APPLI as D, POPULATIONS, fr, logit,
                     nom_variable, propre, taux)

# En production (variable SENTINELLE_PRODUCTION), la documentation interactive de l'API n'est pas exposée.
_PRODUCTION = bool(os.environ.get("SENTINELLE_PRODUCTION"))
app = FastAPI(title="Sentinelle Scolaire", version="1.0",
              description="Risque de décrochage scolaire au primaire, par province du Burkina Faso.",
              docs_url=None if _PRODUCTION else "/docs", redoc_url=None if _PRODUCTION else "/redoc",
              openapi_url=None if _PRODUCTION else "/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

Population = Literal["ensemble", "F", "G"]
SOURCES = [
    "Data Pack du Data Challenge Burkina 2026 : annuaires statistiques de l'éducation, 2016-2017 à 2024-2025",
    "INSD : RGPH 2019 (Mesure et cartographie de la pauvreté, 2022) et annuaires régionaux 2024",
    "Contours administratifs : découpage de 2025 (45 provinces devenues 47, 17 régions)",
]
NB_TOP = 10


def _ligne(t: pd.DataFrame, pcode: str) -> pd.Series:
    lignes = t[t["province_pcode"] == pcode]
    if lignes.empty:
        raise HTTPException(404, f"Province inconnue : {pcode}")
    return lignes.iloc[0]


def _resume(r: pd.Series) -> dict:
    return propre({"pcode": r["province_pcode"], "province": r["province_nom"], "region": r["region_nom"],
                   "taux": r["taux_abandon_prevu"], "borne_basse": r["borne_basse_80"],
                   "borne_haute": r["borne_haute_80"], "classe": r["classe_de_risque"],
                   "taux_actuel": r["taux_abandon_annee_des_variables"],
                   "hausse": bool(r["prevision_au_dessus_du_taux_actuel"]),
                   "score_rupture": r["score_rupture"], "rupture": r["risque_de_rupture"],
                   "scindee": bool(r["province_scindee"]), "ancienne_province": r["province_ancienne_nom"]})


def _seuils(population: str) -> dict:
    return D.fiche(population)["prevision"]["seuils_classes_taux"]


@app.get("/api/meta")
def meta():
    t = D.tableau_ensemble.sort_values(["region_nom", "province_nom"])
    return {"annee_prevue": ANNEE_PREVUE, "annees_projetees": ANNEES_PROJETEES,
            "annee_des_variables": str(t["annee_des_variables"].iloc[0]),
            "populations": POPULATIONS, "date_modele": D.fiche("ensemble")["date"], "sources": SOURCES,
            "provinces": [{"pcode": r.province_pcode, "province": r.province_nom, "region": r.region_nom}
                          for r in t.itertuples()],
            "regions": sorted(t["region_nom"].unique().tolist())}


@app.get("/api/carte")
def carte(population: Population = "ensemble"):
    resumes = {r["province_pcode"]: _resume(r) for _, r in D.tableau(population).iterrows()}
    provinces = json.loads(D.provinces.to_json(drop_id=True))
    for f in provinces["features"]:
        f["properties"].update(resumes.get(f["properties"]["province_pcode"], {}))
    regions = json.loads(D.regions.to_json(drop_id=True))
    return {"provinces": provinces, "regions": regions,
            "etiquettes_regions": D.points_etiquettes(D.regions, "region_nom"),
            "etiquettes_provinces": D.points_etiquettes(D.provinces, "province_pcode"),
            "seuils": _seuils(population)}


def _classe(valeur, seuils: dict) -> str | None:
    if valeur is None or pd.isna(valeur):
        return None
    return "élevé" if valeur >= seuils["eleve"] else ("moyen" if valeur >= seuils["moyen"] else "faible")


def _serie(r: pd.Series, population: str) -> list[dict]:
    """Taux observé de la dernière année puis prévisions à 1, 2 et 3 ans, avec intervalle et classe."""
    seuils = _seuils(population)
    actuel = r["taux_abandon_annee_des_variables"]
    serie = [{"annee": r["annee_des_variables"], "nature": "observé", "taux": actuel, "bas": None, "haut": None,
              "classe": _classe(actuel, seuils)}]
    for x in _projections(r, population):
        serie.append({"annee": x["annee"], "nature": "prévision", "taux": x["taux"], "bas": x["borne_basse"],
                      "haut": x["borne_haute"], "classe": _classe(x["taux"], seuils)})
    return propre(serie)


def _nuage_shap(population: str, n: int = 8) -> dict:
    """Valeurs SHAP signées de chaque province pour les n variables les plus influentes, avec la valeur de la
    variable (rang centile entre provinces, pour la couleur)."""
    contrib = D.explication("contributions", population)
    valeurs = D.explication("valeurs", population)
    noms = D.tableau(population).set_index("province_pcode")["province_nom"]
    variables = [c for c in contrib.columns if c not in ("province_pcode", "sexe", "fille")]
    ordre = contrib[variables].abs().mean().sort_values(ascending=False).index[:n]
    points = []
    for i, v in enumerate(ordre):
        rang = valeurs[v].rank(pct=True)
        for k in range(len(contrib)):
            pcode = contrib["province_pcode"].iloc[k]
            points.append({"v": i, "pcode": pcode, "province": noms.get(pcode, pcode),
                           "shap": round(float(contrib[v].iloc[k]), 3), "valeur": propre(valeurs[v].iloc[k]),
                           "rang": propre(round(float(rang.iloc[k]), 3))})
    return {"variables": [{"variable": v, "libelle": nom_variable(v)} for v in ordre], "points": points}


def _resistantes(population: str, n: int = 6) -> list[dict]:
    """Provinces dont le niveau habituel observé est nettement sous le niveau attendu d'après leurs caractéristiques."""
    f = D.attendu_hors_echantillon(population)
    f = f.sort_values("ecart").head(n)
    return [propre({"pcode": r["province_pcode"], "province": r["province_nom"], "region": r["region_nom"],
                    "observe": round(float(r["niveau_habituel_observe"]), 2),
                    "attendu": round(float(r["attendu"]), 2), "ecart": round(float(r["ecart"]), 2)})
            for _, r in f.iterrows()]


@app.get("/api/national")
def national(population: Population = "ensemble"):
    """Tout le tableau de bord national, pour les quatre années (observé 2024-2025, prévisions jusqu'en 2027-2028)."""
    t = D.tableau(population)
    provinces = []
    for _, r in t.iterrows():
        provinces.append({"pcode": r["province_pcode"], "province": r["province_nom"], "region": r["region_nom"],
                          "scindee": bool(r["province_scindee"]), "ancienne_province": r["province_ancienne_nom"],
                          "score_rupture": propre(r["score_rupture"]), "rupture": r["risque_de_rupture"],
                          "poids": propre(D.poids.get(r["province_pcode"], 1)),
                          "serie": _serie(r, population),
                          "historique": [h["taux"] if not h["rupture"] else None
                                         for h in D.historique(r["province_pcode"], population)]})
    annees = [x["annee"] for x in provinces[0]["serie"]]

    alertes = []
    for _, r in t.sort_values("score_rupture", ascending=False).iterrows():
        if r["risque_de_rupture"] == "élevé":
            alertes.append({"pcode": r["province_pcode"], "province": r["province_nom"], "region": r["region_nom"],
                            "type": "rupture", "valeur": propre(r["score_rupture"])})
    for _, r in t.sort_values("taux_abandon_prevu", ascending=False).iterrows():
        if r["classe_de_risque"] == "élevé" and r["prevision_au_dessus_du_taux_actuel"]:
            alertes.append({"pcode": r["province_pcode"], "province": r["province_nom"], "region": r["region_nom"],
                            "type": "hausse", "valeur": propre(r["taux_abandon_prevu"]),
                            "avant": propre(r["taux_abandon_annee_des_variables"])})

    sexe = []
    for k in range(len(annees)):
        lignes = {}
        for sx in ["F", "G"]:
            for _, r in D.tableau(sx).iterrows():
                lignes.setdefault(r["region_nom"], {})[sx] = lignes.get(r["region_nom"], {}).get(sx, []) + [
                    _serie(r, sx)[k]["taux"]]
        sexe.append([{"region": reg, "filles": propre(float(np.nanmean(v["F"]))),
                      "garcons": propre(float(np.nanmean(v["G"])))} for reg, v in sorted(lignes.items())])

    # Taux national de chaque année : moyenne des provinces pondérée par leurs effectifs de 2024-2025.
    pays = []
    for k, annee in enumerate(annees):
        valeurs = [(p["serie"][k]["taux"], p["poids"]) for p in provinces if p["serie"][k]["taux"] is not None]
        total = sum(w for _, w in valeurs)
        pays.append({"annee": annee, "taux": round(sum(v * w for v, w in valeurs) / total, 2),
                     # Effectifs par sexe non disponibles : le nombre d'abandons ne vaut que pour l'ensemble.
                     "abandons": round(sum(v * w for v, w in valeurs) / 100) if population == "ensemble" else None})

    histo_annees = [h["annee"] for h in D.historique(t["province_pcode"].iloc[0], population)]
    return propre({
        "pays": pays,
        "population": population, "annees": annees, "annees_historique": histo_annees,
        "seuils": _seuils(population), "provinces": provinces, "alertes": alertes, "sexe_par_region": sexe,
        "nuage_shap": _nuage_shap(population), "resistantes": _resistantes(population),
        "erreurs": {"sentinelle": D.erreur_test_final(population),
                    "annee_precedente": D.erreur_test_final(population, "reference_annee_precedente")},
    })


def _cascade(pcode: str, population: str, n: int = 6) -> dict:
    contrib = D.explication("contributions", population)
    valeurs = D.explication("valeurs", population)
    facteurs = D.explication("facteurs", population)
    c = _ligne(contrib, pcode).drop(labels=[k for k in ["province_pcode", "sexe"] if k in contrib.columns])
    v = _ligne(valeurs, pcode)
    c = c.astype(float)
    ordre = c.abs().sort_values(ascending=False).index
    principales = [{"variable": k, "libelle": nom_variable(k), "contribution": round(float(c[k]), 2),
                    "valeur": propre(v.get(k))} for k in ordre[:n]]
    reste = float(c[ordre[n:]].sum())
    return {"base": round(D.valeur_de_base(population), 2), "contributions": principales,
            "autres": round(reste, 2), "niveau_explique": propre(_ligne(facteurs, pcode)["niveau_explique"]),
            "niveau_habituel_observe": propre(_ligne(facteurs, pcode)["niveau_habituel_observe"])}


def _rupture(nom: str, score: float, classe: str) -> dict:
    c = D.contributions_alerte
    ligne = c[c["province_nom"] == nom]
    signaux = []
    if not ligne.empty:
        r = ligne.iloc[0].drop(labels=["province_nom", "constante"]).astype(float)
        signaux = [{"signal": k, "contribution": round(float(x), 3)}
                   for k, x in r.sort_values(key=abs, ascending=False).items()]
    seuils = D.modeles["ensemble"]["fiche"]["alerte_rupture"]["seuils_score"]
    return propre({"score": score, "classe": classe, "seuils": seuils, "signaux": signaux})


def _projections(r: pd.Series, population: str) -> list[dict]:
    marges = D.fiche(population)["prevision"]["marge_conforme_logit_par_horizon"]
    sortie = [{"annee": ANNEE_PREVUE, "horizon": 1, "taux": r["taux_abandon_prevu"],
               "borne_basse": r["borne_basse_80"], "borne_haute": r["borne_haute_80"]}]
    for h, annee in enumerate(ANNEES_PROJETEES, start=2):
        valeur = float(r[f"taux_abandon_prevu_{annee}"])
        z, m = logit(valeur), float(marges[str(h)])
        sortie.append({"annee": annee, "horizon": h, "taux": round(valeur, 2),
                       "borne_basse": round(taux(z - m), 2), "borne_haute": round(taux(z + m), 2)})
    return propre(sortie)


def _synthese(r: pd.Series, cascade: dict) -> str:
    hausses = [c["libelle"] for c in cascade["contributions"] if c["contribution"] > 0][:3]
    texte = (f"{r['province_nom']} : taux d'abandon prévu à {fr(r['taux_abandon_prevu'])} % en {ANNEE_PREVUE} "
             f"(entre {fr(r['borne_basse_80'])} et {fr(r['borne_haute_80'])} % dans 8 cas sur 10), "
             f"risque {r['classe_de_risque']}.")
    if hausses:
        texte += " Caractéristiques qui élèvent son niveau habituel : " + ", ".join(hausses) + "."
    texte += f" Risque de rupture de scolarisation : {r['risque_de_rupture']}."
    return texte


@app.get("/api/province/{pcode}")
def province(pcode: str, population: Population = "ensemble"):
    t = D.tableau(population)
    r = _ligne(t, pcode)
    rang = int(t["taux_abandon_prevu"].rank(ascending=False, method="min")[t["province_pcode"] == pcode].iloc[0])
    cascade = _cascade(pcode, population)
    par_sexe = {}
    for sexe in ["F", "G"]:
        s = D.tableau(sexe)
        if (s["province_pcode"] == pcode).any():
            par_sexe[sexe] = _resume(_ligne(s, pcode))
    return propre({
        "population": population,
        "identite": {"pcode": pcode, "province": r["province_nom"], "region": r["region_nom"],
                     "ancienne_province": r["province_ancienne_nom"], "scindee": bool(r["province_scindee"]),
                     "rang": rang, "provinces": len(t)},
        "prevision": _resume(r),
        "projections": _projections(r, population),
        "historique": {p: D.historique(pcode, p) for p in ["ensemble", "F", "G"]},
        "cascade": cascade,
        "par_sexe": par_sexe,
        "rupture": _rupture(r["province_nom"], r["score_rupture"], r["risque_de_rupture"]),
        "synthese": _synthese(r, cascade),
        "seuils": _seuils(population),
        "annee_des_variables": r["annee_des_variables"],
    })


# Simulateur -----------------------------------------------------------------------------------------

def _elastic():
    return D.modeles["ensemble"]["explication_elastic_net"]


def _niveau(valeurs: pd.Series) -> float:
    e = _elastic()
    n = e["normalisation"]
    x = valeurs[e["variables"]].astype(float).fillna(pd.Series(n["mediane"]))
    z = (x - pd.Series(n["moyenne"])) / pd.Series(n["ecart_type"])
    return float(e["modele"].predict(pd.DataFrame([z.values], columns=e["variables"]))[0])


def _est_part(v: str) -> bool:
    m = D.moyennes_provinces[v]
    return bool(m.min() >= 0 and m.max() <= 1.0001)


@app.get("/api/simulateur/{pcode}")
def leviers(pcode: str):
    r = _ligne(D.tableau_ensemble, pcode)
    e = _elastic()
    m = D.moyennes_provinces
    if pcode not in m.index:
        raise HTTPException(404, f"Province inconnue : {pcode}")
    coef = pd.Series(e["modele"].coef_, index=e["variables"])
    ecart = pd.Series(e["normalisation"]["ecart_type"])
    sortie = []
    for v in e["variables"]:
        if coef[v] == 0:
            continue
        part = _est_part(v)
        echelle = 100 if part else 1
        bas, haut = float(m[v].min()), float(m[v].max())
        marge = (haut - bas) * 0.15
        sortie.append({"variable": v, "libelle": nom_variable(v), "unite": "%" if part else "",
                       "valeur": round(float(m.loc[pcode, v]) * echelle, 2),
                       "minimum": round(max(0.0, bas - marge) * echelle, 2), "maximum": round((haut + marge) * echelle, 2),
                       "mediane_provinces": round(float(m[v].median()) * echelle, 2),
                       "effet_par_unite": round(float(coef[v] / ecart[v]) / echelle, 4)})
    return propre({"pcode": pcode, "province": r["province_nom"], "region": r["region_nom"],
                   "taux": r["taux_abandon_prevu"], "classe": r["classe_de_risque"],
                   "leviers": sortie, "seuils": _seuils("ensemble"),
                   "r2": D.fiche("ensemble")["explication"]["effets_chiffres"]["r2_provinces_non_vues"]})


class Scenario(BaseModel):
    pcode: str
    valeurs: dict[str, float]


@app.post("/api/simulateur")
def simuler(s: Scenario):
    r = _ligne(D.tableau_ensemble, s.pcode)
    m = D.moyennes_provinces
    if s.pcode not in m.index:
        raise HTTPException(404, f"Province inconnue : {s.pcode}")
    actuel = m.loc[s.pcode].copy()
    nouveau = actuel.copy()
    for v, valeur in s.valeurs.items():
        if v in nouveau.index:
            nouveau[v] = valeur / (100 if _est_part(v) else 1)
    ecart = _niveau(nouveau) - _niveau(actuel)
    prevu = float(r["taux_abandon_prevu"])
    simule = min(max(prevu + ecart, 0.0), 100.0)
    seuils = _seuils("ensemble")
    classe = "élevé" if simule >= seuils["eleve"] else ("moyen" if simule >= seuils["moyen"] else "faible")
    return propre({"taux_prevu": prevu, "taux_simule": round(simule, 2), "ecart": round(ecart, 2),
                   "classe_prevue": r["classe_de_risque"], "classe_simulee": classe})


# Assistant ------------------------------------------------------------------------------------------

class Question(BaseModel):
    question: str
    population: Population = "ensemble"
    historique: list[dict] = []


@app.post("/api/assistant")
def assistant(q: Question):
    from assistant import repondre
    return propre(repondre(q.question, q.population, q.historique))


# Mise à jour annuelle -------------------------------------------------------------------------------

class Saisie(BaseModel):
    lignes: list[dict]


class TexteCsv(BaseModel):
    csv: str


@app.get("/api/mise_a_jour/etat")
def etat_mise_a_jour():
    import mise_a_jour as M
    derniere = M.derniere_annee()
    h = M.historique()
    dernier = h[h["annee_scolaire"] == derniere].set_index("province_pcode")
    t = D.tableau_ensemble.sort_values(["region_nom", "province_nom"])
    return propre({"derniere_annee": derniere, "annee_attendue": M.annee_suivante(derniere),
                   "annees_saisies": M.mises_a_jour(),
                   "provinces": [{"pcode": r["province_pcode"], "province": r["province_nom"], "region": r["region_nom"],
                                  "repere_taux": round(float(dernier.loc[r["province_pcode"], "abandon_primaire_precedent"]), 2),
                                  "repere_eleves": int(dernier.loc[r["province_pcode"], "eleves_primaire"])}
                                 for _, r in t.iterrows()]})


@app.get("/api/mise_a_jour/modele.csv")
def modele_mise_a_jour():
    import mise_a_jour as M
    nom = f"sentinelle_donnees_{M.annee_suivante(M.derniere_annee())}.csv"
    return Response("\ufeff" + M.modele_csv(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})


@app.post("/api/mise_a_jour/lire")
def lire_mise_a_jour(c: TexteCsv):
    import mise_a_jour as M
    try:
        return {"lignes": propre(M.lire_csv(c.csv))}
    except Exception as e:
        raise HTTPException(400, f"Fichier illisible : {e}") from e


@app.post("/api/mise_a_jour/apercu")
def apercu_mise_a_jour(s: Saisie):
    import mise_a_jour as M
    sortie = M.calculer(s.lignes)
    sortie.pop("lignes_valides", None)
    return propre(sortie)


@app.post("/api/mise_a_jour/enregistrer")
def enregistrer_mise_a_jour(s: Saisie):
    import mise_a_jour as M
    return propre(M.enregistrer(s.lignes))


@app.get("/api/mise_a_jour/previsions/{annee}.csv")
def previsions_mise_a_jour(annee: str):
    import mise_a_jour as M
    chemin = M.DOSSIER / f"previsions_{annee}.csv"
    if annee not in M.mises_a_jour() or not chemin.exists():
        raise HTTPException(404, f"Aucune mise à jour enregistrée pour {annee}")
    return Response(chemin.read_bytes(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="sentinelle_previsions_depuis_{annee}.csv"'})


@app.delete("/api/mise_a_jour/{annee}")
def annuler_mise_a_jour(annee: str):
    import mise_a_jour as M
    if not M.annuler(annee):
        raise HTTPException(400, "Seule la dernière année saisie peut être retirée.")
    return {"retire": annee}


# Rapports PDF ---------------------------------------------------------------------------------------

def _pdf(contenu: bytes, nom: str) -> Response:
    return Response(contenu, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{nom}"'})


# Leviers d'action : variables sur lesquelles l'administration peut agir, avec le sens qui réduit l'abandon.
LEVIERS_ACTION = [
    ("deficit_places_pour_100_eleves_primaire", "baisser", "Tables-bancs et nouvelles salles de classe"),
    ("tbs_prescolaire_region", "hausser", "Ouvrir des classes de préscolaire"),
    ("part_enseignants_primaire_debutants", "baisser", "Accompagner les débutants, stabiliser les affectations"),
    ("part_salles_primaire_murs_precaires", "baisser", "Remplacer les salles en matériaux précaires"),
    ("part_enseignantes_primaire", "hausser", "Recruter et affecter davantage d'enseignantes"),
    ("part_ecoles_primaires_electricite", "hausser", "Électrifier les écoles (solaire)"),
    ("part_ecoles_primaires_cantine", "hausser", "Étendre les cantines scolaires"),
    ("part_ecoles_primaires_eau_potable", "hausser", "Points d'eau potable dans les écoles"),
]
# Variables du modèle qui décrivent la situation sans être une action directe.
SIGNAUX = {"part_cp1": "Signal à surveiller : un CP1 très chargé traduit des entrées tardives, des redoublements et des "
                       "départs avant le CM2 ; on agit sur ses causes (préscolaire, suivi des élèves dès le CP1).",
           "ni_ecole_ni_emploi_15_24_province": "Levier interministériel : programmes d'emploi et de formation des jeunes.",
           "deficit_places_pour_100_eleves_primaire": "Levier d'action : tables-bancs et salles de classe."}


@app.get("/api/leviers_action/{pcode}")
def leviers_action(pcode: str):
    """Leviers d'action : lien mesuré entre provinces (moyennes 2016-2025) et écart de la province à la médiane."""
    m = D.base.groupby("province_pcode").mean(numeric_only=True)
    if pcode not in m.index:
        raise HTTPException(404, f"Province inconnue : {pcode}")
    cible = m["abandon_primaire_precedent"]
    sortie = []
    for v, sens, action in LEVIERS_ACTION:
        echelle = 100 if m[v].max() <= 1.0 else 1
        lien = float(m[v].corr(cible, method="spearman"))
        valeur, mediane = float(m.loc[pcode, v]) * echelle, float(m[v].median()) * echelle
        defavorable = valeur > mediane if sens == "baisser" else valeur < mediane
        libelle = nom_variable(v) if nom_variable(v) != v else "écoles avec cantine"
        sortie.append({"variable": v, "libelle": libelle, "action": action, "sens": sens,
                       "lien": round(lien, 2), "valeur": round(valeur, 1), "mediane": round(mediane, 1),
                       "unite": "%" if echelle == 100 or v.startswith("tbs") else " pour 100 élèves",
                       "a_ameliorer": bool(defavorable)})
    sortie.sort(key=lambda x: (not x["a_ameliorer"], -abs(x["lien"])))
    return propre({"pcode": pcode, "leviers": sortie, "signaux": SIGNAUX})


# Ordres d'enseignement après le primaire : valeurs observées seulement (quatre années publiées, pas de prévision).
ORDRES = {
    "post_primaire": {"abandon": "abandon_post_primaire_province", "entree": "tba_6e_province",
                      "achevement": "achevement_post_primaire_province"},
    "secondaire": {"abandon": "abandon_secondaire_province", "entree": "tba_2nde_province",
                   "achevement": "achevement_secondaire_province"},
}
SEUILS_ORDRES = {"moyen": 15.0, "eleve": 30.0}


def _annees_observees(variable: str) -> list[str]:
    import donnees
    statuts = pd.read_csv(donnees.BASE / "statut_cellules_par_sexe.csv", sep=";", encoding="utf-8-sig",
                          usecols=["annee_scolaire", "variable", "statut"])
    v = statuts[statuts["variable"] == variable]
    part = v.groupby("annee_scolaire")["statut"].agg(lambda x: (x == "observée").mean())
    return sorted(part[part >= 0.5].index)


def _table_ordre(ordre: str, population: str) -> pd.DataFrame:
    """Province × année : abandon, entrée, achèvement. Ensemble du secondaire : moyenne des filles et des garçons."""
    colonnes = list(ORDRES[ordre].values())
    cles = ["province_pcode", "province_nom", "region_nom", "annee_scolaire"]
    if population != "ensemble":
        t = D.base_sexe[D.base_sexe["sexe"] == population]
    elif ordre == "post_primaire":
        t = D.base
    else:
        t = D.base_sexe.groupby(cles, as_index=False)[colonnes].mean()
    return t[cles + colonnes]


def _interpretable(taux: float) -> bool:
    # 0 % ou plus de 90 % : presque aucun élève (écoles fermées), taux non interprétable.
    return 1 < taux < 90


@app.get("/api/ordre/{ordre}")
def vue_ordre(ordre: Literal["post_primaire", "secondaire"], population: Population = "ensemble"):
    v = ORDRES[ordre]
    annees = _annees_observees(v["abandon"])
    t = _table_ordre(ordre, population).set_index(["province_pcode", "annee_scolaire"])
    provinces = []
    for pcode in t.index.get_level_values(0).unique():
        serie = []
        for a in annees:
            r = t.loc[(pcode, a)]
            taux_a = round(float(r[v["abandon"]]), 1)
            serie.append({"annee": a, "taux": taux_a if _interpretable(taux_a) else None,
                          "classe": _classe(taux_a, SEUILS_ORDRES) if _interpretable(taux_a) else None,
                          "entree": propre(round(float(r[v["entree"]]), 1)),
                          "achevement": propre(round(float(r[v["achevement"]]), 1))})
        r = t.loc[(pcode, annees[-1])]
        provinces.append({"pcode": pcode, "province": r["province_nom"], "region": r["region_nom"], "serie": serie})
    medianes = []
    for k, a in enumerate(annees):
        valeurs = [p["serie"][k]["taux"] for p in provinces if p["serie"][k]["taux"] is not None]
        medianes.append({"annee": a, "mediane": round(float(np.median(valeurs)), 1),
                         "non_interpretables": len(provinces) - len(valeurs)})
    regions = []
    for reg in sorted({p["region"] for p in provinces}):
        valeurs = [[p["serie"][k]["taux"] for p in provinces if p["region"] == reg] for k in range(len(annees))]
        regions.append({"region": reg, "serie": [propre(round(float(np.median([x for x in vk if x is not None])), 1))
                                                 if any(x is not None for x in vk) else None for vk in valeurs]})
    return propre({"ordre": ordre, "population": population, "annees": annees, "seuils": SEUILS_ORDRES,
                   "provinces": provinces, "medianes": medianes, "regions": regions})


@app.get("/api/comparaison_ordres")
def comparaison_ordres(population: Population = "ensemble"):
    """Abandon de la province médiane, primaire, post-primaire et secondaire, sur les années observées communes."""
    annees = _annees_observees(ORDRES["post_primaire"]["abandon"])
    base = D.base if population == "ensemble" else D.base_sexe[D.base_sexe["sexe"] == population]
    filtre = base["abandon_primaire_precedent"].map(_interpretable)
    primaire = base[filtre].groupby("annee_scolaire")["abandon_primaire_precedent"].median()
    series = {"primaire": [propre(round(float(primaire[a]), 1)) for a in annees]}
    for ordre in ORDRES:
        vue = vue_ordre(ordre, population)
        series[ordre] = [m["mediane"] for m in vue["medianes"]]
    return propre({"annees": annees, "series": series})


@app.get("/api/telechargement/previsions")
def telecharger_previsions(population: Population = "ensemble", region: str | None = None):
    """Base des prévisions en CSV pour Excel : une ligne par province et par année, de 2024-2025 à 2027-2028."""
    n = national(population)
    lignes = []
    for p in n["provinces"]:
        if region and p["region"] != region:
            continue
        for s in p["serie"]:
            lignes.append({
                "province_pcode": p["pcode"], "province": p["province"], "region": p["region"],
                "province_avant_2025": p["ancienne_province"], "province_creee_en_2025": "oui" if p["scindee"] else "non",
                "population": POPULATIONS[population], "annee_scolaire": s["annee"], "nature": s["nature"],
                "taux_abandon_pct": s["taux"], "borne_basse_80_pct": s["bas"], "borne_haute_80_pct": s["haut"],
                "classe_de_risque": s["classe"], "eleves_2024_2025": int(p["poids"]) if p["poids"] else None,
                "abandons_estimes": round(s["taux"] * p["poids"] / 100) if p["poids"] else None,
                "score_rupture_2025_2026": p["score_rupture"], "risque_de_rupture": p["rupture"],
            })
    if not lignes:
        raise HTTPException(404, f"Région inconnue : {region}")
    # Séparateur « ; » et virgule décimale : le fichier s'ouvre tel quel dans Excel en français.
    contenu = pd.DataFrame(lignes).to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig")
    suffixe = f"_{region}" if region else ""
    nom = f"sentinelle_previsions_2025_2028{suffixe}_{population}.csv"
    return Response(contenu, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})


@app.get("/api/rapport/national")
def rapport_national(population: Population = "ensemble"):
    import rapport
    return _pdf(rapport.rapport_national(population), f"sentinelle_rapport_national_{population}.pdf")


@app.get("/api/rapport/province/{pcode}")
def rapport_province(pcode: str, population: Population = "ensemble"):
    import rapport
    nom = _ligne(D.tableau_ensemble, pcode)["province_nom"]
    return _pdf(rapport.rapport_province(pcode, population), f"sentinelle_rapport_{nom}_{population}.pdf")


@app.get("/api/rapport/region/{nom}")
def rapport_region(nom: str, population: Population = "ensemble"):
    import rapport
    try:
        return _pdf(rapport.rapport_region(nom, population), f"sentinelle_rapport_region_{nom}_{population}.pdf")
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
