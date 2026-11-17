"""Assistant Sentinelle : répond aux questions de décision à partir des données du tableau de bord.

Les chiffres viennent toujours des outils ci-dessous, qui lisent les sorties de l'analyse. Deux modes :

- avec la variable d'environnement ``GEMINI_API_KEY`` : le modèle Gemini choisit les outils à appeler et rédige
  la réponse à partir de leurs résultats (il ne doit citer aucun chiffre qui n'en vient pas) ;
- sans clé, ou si le service ne répond pas : un mode hors ligne reconnaît la question (province, région,
  comparaison, priorités, ruptures, facteurs, filles et garçons) et répond par des phrases construites sur les
  mêmes outils.

Aucune donnée individuelle n'est transmise : seulement des taux agrégés par province.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.error
import urllib.request

import pandas as pd

from donnees import DONNEES_APPLI as D, fr

MODELE_GEMINI = os.environ.get("GEMINI_MODELE", "gemini-2.5-flash")
SOURCE_BASE = "Base apurée 2016-2017 à 2024-2025 (Data Pack du Data Challenge, annuaires de l'éducation)"
SOURCE_PREVISION = "Prévision Sentinelle : retour amorti vers le niveau habituel de la province, intervalle conforme à 80 %"
SOURCE_SHAP = "Facteurs : LightGBM et valeurs SHAP (associations, pas causes)"
SOURCE_RUPTURE = "Alerte de rupture : régression logistique sur sept signaux"
ANNEES = ["2024-2025", "2025-2026", "2026-2027", "2027-2028"]


def _sans_accent(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn")


def _tableau(population: str) -> pd.DataFrame:
    return D.tableau(population)


def _pct(x) -> str:
    return "n.d." if x is None or pd.isna(x) else f"{fr(float(x))} %"


# Outils -------------------------------------------------------------------------------------------

def fiche_province(pcode: str, population: str = "ensemble") -> dict:
    from main import _cascade, _projections, _ligne
    t = _tableau(population)
    r = _ligne(t, pcode)
    rang = int(t["taux_abandon_prevu"].rank(ascending=False, method="min")[t["province_pcode"] == pcode].iloc[0])
    cascade = _cascade(pcode, population, n=4)
    sexe = {}
    for s in ["F", "G"]:
        ts = _tableau(s)
        if (ts["province_pcode"] == pcode).any():
            sexe["filles" if s == "F" else "garcons"] = float(_ligne(ts, pcode)["taux_abandon_prevu"])
    return {
        "province": r["province_nom"], "region": r["region_nom"], "pcode": pcode,
        "taux_2024_2025_observe": float(r["taux_abandon_annee_des_variables"]),
        "previsions": _projections(r, population), "classe": r["classe_de_risque"], "rang": rang, "sur": len(t),
        "facteurs_principaux": [{"facteur": c["libelle"], "points": c["contribution"]} for c in cascade["contributions"]],
        "niveau_attendu": cascade["niveau_explique"], "moyenne_provinces": cascade["base"],
        "score_rupture": float(r["score_rupture"]), "risque_rupture": r["risque_de_rupture"], "par_sexe_2025_2026": sexe,
        "sources": [SOURCE_BASE, SOURCE_PREVISION, SOURCE_SHAP, SOURCE_RUPTURE],
    }


def classement(population: str = "ensemble", n: int = 5, region: str | None = None, annee: str = "2025-2026") -> dict:
    from main import _serie
    t = _tableau(population)
    if region:
        t = t[t["region_nom"].map(_sans_accent) == _sans_accent(region)]
    k = ANNEES.index(annee) if annee in ANNEES else 1
    lignes = []
    for _, r in t.iterrows():
        s = _serie(r, population)[k]
        lignes.append({"province": r["province_nom"], "pcode": r["province_pcode"], "region": r["region_nom"],
                       "taux": s["taux"], "bas": s["bas"], "haut": s["haut"], "classe": s["classe"],
                       "rupture": r["risque_de_rupture"]})
    lignes.sort(key=lambda x: -(x["taux"] or 0))
    return {"annee": ANNEES[k], "region": region, "provinces": lignes[: max(1, int(n))], "total": len(lignes),
            "sources": [SOURCE_BASE, SOURCE_PREVISION]}


def synthese_region(region: str, population: str = "ensemble") -> dict:
    c = classement(population, n=50, region=region)
    if not c["provinces"]:
        return {"erreur": f"Région inconnue : {region}"}
    t = _tableau(population)
    g = t[t["region_nom"].map(_sans_accent) == _sans_accent(region)].copy()
    g["poids"] = g["province_pcode"].map(D.poids).fillna(1)
    pondere = float((g["taux_abandon_prevu"] * g["poids"]).sum() / g["poids"].sum())
    return {"region": g["region_nom"].iloc[0], "taux_pondere_2025_2026": round(pondere, 2), "provinces": c["provinces"],
            "alertes_rupture": [p["province"] for p in c["provinces"] if p["rupture"] == "élevé"],
            "sources": [SOURCE_BASE, SOURCE_PREVISION, SOURCE_RUPTURE]}


def alertes_rupture(population: str = "ensemble") -> dict:
    t = _tableau(population).sort_values("score_rupture", ascending=False)
    t = t[t["risque_de_rupture"] == "élevé"]
    return {"provinces": [{"province": r["province_nom"], "pcode": r["province_pcode"], "region": r["region_nom"],
                           "score": float(r["score_rupture"])} for _, r in t.iterrows()],
            "sources": [SOURCE_RUPTURE]}


def provinces_resistantes(population: str = "ensemble") -> dict:
    from main import _resistantes
    return {"provinces": _resistantes(population), "sources": [SOURCE_BASE, SOURCE_SHAP]}


def facteurs_nationaux(population: str = "ensemble") -> dict:
    t = D.explication("importance", population).head(6)
    return {"facteurs": [{"facteur": r["libelle"], "contribution_moyenne_points": float(r["contribution_absolue_moyenne_points"]),
                          "sens": r["sens"]} for _, r in t.iterrows()], "sources": [SOURCE_SHAP]}


def ecarts_filles_garcons() -> dict:
    f = _tableau("F").set_index("province_pcode")
    g = _tableau("G").set_index("province_pcode")
    e = (f["taux_abandon_prevu"] - g["taux_abandon_prevu"]).dropna()
    lignes = [{"province": f.loc[p, "province_nom"], "pcode": p, "region": f.loc[p, "region_nom"],
               "filles": float(f.loc[p, "taux_abandon_prevu"]), "garcons": float(g.loc[p, "taux_abandon_prevu"]),
               "ecart": round(float(v), 2)} for p, v in e.sort_values(ascending=False).items()]
    return {"filles_plus_exposees": lignes[:5], "garcons_plus_exposes": lignes[::-1][:5],
            "provinces_filles_au_dessus": int((e > 0).sum()), "total": len(e), "sources": [SOURCE_BASE, SOURCE_PREVISION]}


OUTILS = {
    "fiche_province": (fiche_province, "Fiche d'une province : taux observé 2024-2025, prévisions 2025-2026 à 2027-2028 avec intervalle, classe, rang, facteurs, rupture, filles et garçons.",
                       {"pcode": {"type": "string", "description": "Code de la province, par exemple BF5401"}}),
    "classement": (classement, "Provinces au taux prévu le plus élevé, pour le pays ou une région, pour une année (2024-2025 à 2027-2028).",
                   {"n": {"type": "integer"}, "region": {"type": "string"}, "annee": {"type": "string"}}),
    "synthese_region": (synthese_region, "Synthèse d'une région : taux pondéré, provinces classées, alertes de rupture.",
                        {"region": {"type": "string"}}),
    "alertes_rupture": (alertes_rupture, "Provinces en alerte élevée de rupture de scolarisation (fermetures, départs).", {}),
    "provinces_resistantes": (provinces_resistantes, "Provinces dont le niveau d'abandon est nettement sous celui attendu d'après leurs caractéristiques.", {}),
    "facteurs_nationaux": (facteurs_nationaux, "Caractéristiques les plus associées au niveau d'abandon des provinces, avec leur sens.", {}),
    "ecarts_filles_garcons": (ecarts_filles_garcons, "Écarts de taux prévu entre filles et garçons par province.", {}),
}


# Reconnaissance des noms ----------------------------------------------------------------------------

def _trouver(question: str) -> tuple[list[dict], list[str]]:
    q = _sans_accent(question)
    t = D.tableau_ensemble
    provinces, regions = [], []
    demande_region = "region" in q
    for _, r in t.iterrows():
        nom = _sans_accent(r["province_nom"])
        if re.search(rf"\b{re.escape(nom)}\b", q):
            provinces.append({"pcode": r["province_pcode"], "province": r["province_nom"]})
    for nom in sorted(t["region_nom"].unique()):
        if re.search(rf"\b{re.escape(_sans_accent(nom))}\b", q):
            regions.append(nom)
    # Kadiogo et Sourou sont à la fois province et région : le mot « région » tranche.
    if demande_region:
        provinces = [p for p in provinces if p["province"] not in regions]
    else:
        regions = [r for r in regions if r not in [p["province"] for p in provinces]]
    vus, uniques = set(), []
    for p in provinces:
        if p["pcode"] not in vus:
            vus.add(p["pcode"])
            uniques.append(p)
    return uniques, regions


# Mode hors ligne ------------------------------------------------------------------------------------

def _texte_fiche(f: dict) -> str:
    p = f["previsions"]
    facteurs = ", ".join(x["facteur"] for x in f["facteurs_principaux"] if x["points"] > 0) or "aucun au-dessus de la moyenne"
    sexe = f["par_sexe_2025_2026"]
    lignes = [
        f"**{f['province']}** (région {f['region']}) : {_pct(f['taux_2024_2025_observe'])} observé en 2024-2025.",
        f"Prévision 2025-2026 : **{_pct(p[0]['taux'])}** (entre {_pct(p[0]['borne_basse'])} et {_pct(p[0]['borne_haute'])} dans 8 cas sur 10), "
        f"risque {f['classe']}, {f['rang']}{'er' if f['rang'] == 1 else 'e'} sur {f['sur']}.",
        f"2026-2027 et 2027-2028 : {_pct(p[1]['taux'])} et {_pct(p[2]['taux'])}, avec des intervalles plus larges.",
        f"Ce qui élève son niveau : {facteurs}.",
        f"Risque de rupture de scolarisation : {f['risque_rupture']} (score {fr(f['score_rupture'], 2)}).",
    ]
    if sexe:
        lignes.append(f"Filles {_pct(sexe.get('filles'))}, garçons {_pct(sexe.get('garcons'))} en 2025-2026.")
    return "\n".join(lignes)


def _hors_ligne(question: str, population: str) -> tuple[str, list[str], list[dict]]:
    q = _sans_accent(question)
    provinces, regions = _trouver(question)
    annee = next((a for a in ANNEES if a in question), "2025-2026")

    if len(provinces) >= 2:
        fiches = [fiche_province(p["pcode"], population) for p in provinces[:4]]
        lignes = ["Comparaison (prévision 2025-2026) :"]
        for f in sorted(fiches, key=lambda x: -x["previsions"][0]["taux"]):
            lignes.append(f"- **{f['province']}** : {_pct(f['previsions'][0]['taux'])}, risque {f['classe']}, rupture {f['risque_rupture']}, "
                          f"premier facteur : {f['facteurs_principaux'][0]['facteur']}.")
        premiere = max(fiches, key=lambda x: x["previsions"][0]["taux"])
        lignes.append(f"Priorité : {premiere['province']}, au taux prévu le plus élevé.")
        return "\n".join(lignes), fiches[0]["sources"], provinces[:4]

    if len(provinces) == 1:
        f = fiche_province(provinces[0]["pcode"], population)
        return _texte_fiche(f), f["sources"], provinces

    if regions:
        s = synthese_region(regions[0], population)
        lignes = [f"**Région {s['region']}** : taux pondéré prévu {_pct(s['taux_pondere_2025_2026'])} en 2025-2026."]
        for p in s["provinces"][:6]:
            lignes.append(f"- {p['province']} : {_pct(p['taux'])} (risque {p['classe']}{', alerte de rupture' if p['rupture'] == 'élevé' else ''})")
        if s["alertes_rupture"]:
            lignes.append(f"À prioriser : {', '.join(s['alertes_rupture'])} (rupture probable).")
        return "\n".join(lignes), s["sources"], [{"pcode": p["pcode"], "province": p["province"]} for p in s["provinces"][:6]]

    if any(m in q for m in ["rupture", "fermeture", "alerte", "deplace"]):
        a = alertes_rupture(population)
        lignes = [f"{len(a['provinces'])} provinces en alerte élevée de rupture de scolarisation :"]
        lignes += [f"- {p['province']} ({p['region']}) : score {fr(p['score'], 2)}" for p in a["provinces"]]
        return "\n".join(lignes), a["sources"], a["provinces"][:8]

    if any(m in q for m in ["resist", "bonne pratique", "exemple", "modele a suivre"]):
        r = provinces_resistantes(population)
        lignes = ["Provinces dont le niveau habituel est nettement sous celui attendu d'après leurs caractéristiques :"]
        lignes += [f"- {p['province']} ({p['region']}) : {_pct(p['observe'])} contre {_pct(p['attendu'])} attendu" for p in r["provinces"]]
        lignes.append("Des pratiques locales à étudier et, si elles se confirment, à reproduire.")
        return "\n".join(lignes), r["sources"], r["provinces"]

    if any(m in q for m in ["fille", "garcon", "sexe", "genre"]):
        e = ecarts_filles_garcons()
        lignes = [f"Les filles ont un taux prévu supérieur à celui des garçons dans {e['provinces_filles_au_dessus']} provinces sur {e['total']}.",
                  "Écarts les plus marqués au détriment des filles :"]
        lignes += [f"- {p['province']} : filles {_pct(p['filles'])}, garçons {_pct(p['garcons'])}" for p in e["filles_plus_exposees"][:3]]
        lignes.append("Au détriment des garçons :")
        lignes += [f"- {p['province']} : garçons {_pct(p['garcons'])}, filles {_pct(p['filles'])}" for p in e["garcons_plus_exposes"][:3]]
        return "\n".join(lignes), e["sources"], e["filles_plus_exposees"][:3]

    if any(m in q for m in ["facteur", "pourquoi", "cause", "explique", "shap"]):
        f = facteurs_nationaux(population)
        lignes = ["Caractéristiques les plus associées au niveau d'abandon des provinces :"]
        lignes += [f"- {x['facteur']} : {x['sens']}" for x in f["facteurs"]]
        lignes.append("Ce sont des associations entre provinces, pas des causes démontrées.")
        return "\n".join(lignes), f["sources"], []

    if any(m in q for m in ["priorit", "classement", "plus eleve", "top", "pire", "risque", "ou agir", "cibler"]):
        c = classement(population, n=5, annee=annee)
        lignes = [f"Provinces au taux le plus élevé en {c['annee']} :"]
        lignes += [f"{i + 1}. **{p['province']}** ({p['region']}) : {_pct(p['taux'])}" + (f" [{_pct(p['bas'])} ; {_pct(p['haut'])}]" if p["bas"] else "")
                   for i, p in enumerate(c["provinces"])]
        ruptures = [p["province"] for p in c["provinces"] if p["rupture"] == "élevé"]
        if ruptures:
            lignes.append(f"Dont en alerte de rupture : {', '.join(ruptures)}.")
        return "\n".join(lignes), c["sources"], c["provinces"]

    aide = ("Je réponds à partir des données du tableau de bord. Exemples :\n"
            "- « Où agir en priorité en 2025-2026 ? »\n- « Compare Loroum et Yagha »\n- « Que se passe-t-il dans la région Soum ? »\n"
            "- « Quelles provinces risquent une rupture ? »\n- « Quelles provinces résistent ? »\n- « Où les filles sont-elles plus exposées ? »")
    return aide, [], []


# Mode Gemini ----------------------------------------------------------------------------------------

CONSIGNE = (
    "Tu es l'assistant de Sentinelle Scolaire, tableau de bord du risque de décrochage au primaire au Burkina Faso "
    "(47 provinces, 17 régions, découpage de 2025). Réponds en français, en phrases courtes, pour un décideur. "
    "N'utilise que les chiffres renvoyés par les outils ; si une information manque, dis-le. Les facteurs sont des "
    "associations, pas des causes. Les taux sont en pourcentage avec une virgule décimale. Termine par une "
    "recommandation concrète quand la question s'y prête. Codes des provinces : {codes}."
)


def _declarations() -> list[dict]:
    sortie = []
    for nom, (_, description, proprietes) in OUTILS.items():
        d = {"name": nom, "description": description}
        if proprietes:
            d["parameters"] = {"type": "object", "properties": proprietes}
        sortie.append(d)
    return sortie


def _appeler_gemini(cle: str, contenus: list, consigne: str) -> dict:
    corps = {"systemInstruction": {"parts": [{"text": consigne}]}, "contents": contenus,
             "tools": [{"functionDeclarations": _declarations()}], "generationConfig": {"temperature": 0.2}}
    requete = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODELE_GEMINI}:generateContent",
        data=json.dumps(corps).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": cle}, method="POST")
    with urllib.request.urlopen(requete, timeout=25) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


def _gemini(question: str, population: str, cle: str) -> tuple[str, list[str], list[dict]]:
    codes = ", ".join(f"{r.province_nom}={r.province_pcode}" for r in D.tableau_ensemble.itertuples())
    consigne = CONSIGNE.format(codes=codes)
    contenus = [{"role": "user", "parts": [{"text": question}]}]
    sources: list[str] = []
    liens: list[dict] = []
    for _ in range(5):
        r = _appeler_gemini(cle, contenus, consigne)
        parties = r["candidates"][0]["content"].get("parts", [])
        appels = [p["functionCall"] for p in parties if "functionCall" in p]
        if not appels:
            texte = "".join(p.get("text", "") for p in parties).strip()
            return texte, sorted(set(sources)), liens
        contenus.append({"role": "model", "parts": parties})
        reponses = []
        for appel in appels:
            fonction = OUTILS.get(appel["name"], (None,))[0]
            arguments = dict(appel.get("args") or {})
            if "population" in fonction.__code__.co_varnames:
                arguments.setdefault("population", population)
            try:
                resultat = fonction(**arguments) if fonction else {"erreur": "outil inconnu"}
            except Exception as e:  # une erreur d'outil est rendue au modèle, qui peut se corriger
                resultat = {"erreur": str(e)}
            sources += resultat.get("sources", []) if isinstance(resultat, dict) else []
            for cle_liste in ["provinces", "filles_plus_exposees"]:
                for p in (resultat.get(cle_liste) or [])[:6] if isinstance(resultat, dict) else []:
                    if isinstance(p, dict) and "pcode" in p:
                        liens.append({"pcode": p["pcode"], "province": p["province"]})
            if isinstance(resultat, dict) and "pcode" in resultat:
                liens.append({"pcode": resultat["pcode"], "province": resultat["province"]})
            reponses.append({"functionResponse": {"name": appel["name"], "response": json.loads(json.dumps(resultat, default=str))}})
        contenus.append({"role": "user", "parts": reponses})
    raise RuntimeError("trop d'appels d'outils")


def repondre(question: str, population: str = "ensemble") -> dict:
    question = (question or "").strip()[:500]
    cle = os.environ.get("GEMINI_API_KEY", "").strip()
    if cle and question:
        try:
            texte, sources, liens = _gemini(question, population, cle)
            if texte:
                vus = {}
                for l in liens:
                    vus.setdefault(l["pcode"], l)
                return {"reponse": texte, "sources": sources, "liens": list(vus.values())[:6], "mode": "gemini"}
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, RuntimeError, ValueError):
            pass
    texte, sources, liens = _hors_ligne(question, population)
    return {"reponse": texte, "sources": sources,
            "liens": [{"pcode": l["pcode"], "province": l["province"]} for l in liens if "pcode" in l][:6],
            "mode": "hors ligne"}
