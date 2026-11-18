"""Mise à jour annuelle : nouvelles données d'une année, nouvelles prévisions, sans réentraîner les modèles.

L'utilisateur apporte, pour chaque province, le taux d'abandon du primaire de la nouvelle année et l'effectif du
primaire (et, s'il les a, les taux des filles et des garçons). Le calcul reprend exactement la règle du modèle
retenu :

- niveau habituel = moyenne des taux de la province, années de rupture exclues (variation des effectifs de plus
  de 30 %) ;
- prévisions des trois années suivantes : modèle retenu dans la fiche du modèle. Pour le retour amorti,
  z(t+h) = logit(niveau) + φ^h × (logit(taux de l'année) - logit(niveau)), écart nul si l'année est une rupture ;
  pour le niveau habituel, le niveau lui-même. Marges conformes sauvegardées (échelle logit) ;
- classes de risque avec les seuils sauvegardés ;
- score de rupture avec le modèle d'alerte sauvegardé, recalculé sur les nouveaux signaux.

Les données saisies sont rangées à part, dans ``data/05_mises_a_jour/`` : elles ne modifient ni les données des
organisateurs ni la base apurée. Pour la vue par sexe, la rupture de la nouvelle année est jugée sur les effectifs
de l'ensemble.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd

from donnees import DONNEES, DONNEES_APPLI as D, SEUIL_RUPTURE, logit, taux

DOSSIER = DONNEES / "05_mises_a_jour"
COLONNES = ["province_pcode", "province_nom", "region_nom", "annee_scolaire", "taux_abandon_primaire",
            "eleves_primaire", "taux_abandon_filles", "taux_abandon_garcons"]
OBLIGATOIRES = ["province_pcode", "taux_abandon_primaire", "eleves_primaire"]


def annee_suivante(annee: str) -> str:
    debut = int(annee[:4])
    return f"{debut + 1}-{debut + 2}"


def mises_a_jour() -> list[str]:
    if not DOSSIER.exists():
        return []
    return sorted(p.stem for p in DOSSIER.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9].csv"))


def _saisies() -> pd.DataFrame:
    tables = [pd.read_csv(DOSSIER / f"{a}.csv", sep=";", encoding="utf-8-sig", dtype={"province_pcode": str})
              for a in mises_a_jour()]
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(columns=COLONNES)


def historique() -> pd.DataFrame:
    """Base apurée (ensemble) prolongée par les années déjà saisies : une ligne par province et par année."""
    b = D.base[["province_pcode", "province_nom", "region_nom", "annee_scolaire", "abandon_primaire_precedent",
                "eleves_primaire", "evolution_eleves_primaire", "abandons_primaire_orpaillage_pour_1000_region",
                "hors_ecole_16_18_province"]].copy()
    s = _saisies()
    if len(s):
        lignes = []
        for _, r in s.sort_values("annee_scolaire").iterrows():
            avant = pd.concat([b, pd.DataFrame(lignes)]) if lignes else b
            precedent = avant[avant["province_pcode"] == r["province_pcode"]].sort_values("annee_scolaire").iloc[-1]
            lignes.append({**precedent.to_dict(), "annee_scolaire": r["annee_scolaire"],
                           "abandon_primaire_precedent": float(r["taux_abandon_primaire"]),
                           "eleves_primaire": float(r["eleves_primaire"]),
                           "evolution_eleves_primaire": float(r["eleves_primaire"]) / max(float(precedent["eleves_primaire"]), 1) - 1})
        b = pd.concat([b, pd.DataFrame(lignes)], ignore_index=True)
    return b.sort_values(["province_pcode", "annee_scolaire"]).reset_index(drop=True)


def historique_sexe() -> pd.DataFrame:
    b = D.base_sexe[["province_pcode", "sexe", "annee_scolaire", "abandon_primaire_precedent",
                     "evolution_eleves_primaire"]].copy()
    s = _saisies()
    if len(s):
        h = historique()
        evolution = h.set_index(["province_pcode", "annee_scolaire"])["evolution_eleves_primaire"]
        lignes = []
        for _, r in s.iterrows():
            for sexe, col in [("F", "taux_abandon_filles"), ("G", "taux_abandon_garcons")]:
                if pd.notna(r.get(col)):
                    lignes.append({"province_pcode": r["province_pcode"], "sexe": sexe, "annee_scolaire": r["annee_scolaire"],
                                   "abandon_primaire_precedent": float(r[col]),
                                   "evolution_eleves_primaire": evolution.get((r["province_pcode"], r["annee_scolaire"]), 0.0)})
        b = pd.concat([b, pd.DataFrame(lignes)], ignore_index=True)
    return b


def derniere_annee() -> str:
    return str(historique()["annee_scolaire"].max())


def _niveau(g: pd.DataFrame) -> float:
    propre = g.loc[g["evolution_eleves_primaire"].abs() <= SEUIL_RUPTURE, "abandon_primaire_precedent"]
    return float(propre.mean() if len(propre) else g["abandon_primaire_precedent"].mean())


def modele_csv() -> str:
    """Fichier à remplir : une ligne par province, avec les valeurs de la dernière année pour repère."""
    h = historique()
    annee = derniere_annee()
    nouvelle = annee_suivante(annee)
    dernier = h[h["annee_scolaire"] == annee].set_index("province_pcode")
    t = D.tableau_ensemble.sort_values(["region_nom", "province_nom"])
    lignes = []
    for _, r in t.iterrows():
        d = dernier.loc[r["province_pcode"]]
        lignes.append({"province_pcode": r["province_pcode"], "province_nom": r["province_nom"], "region_nom": r["region_nom"],
                       "annee_scolaire": nouvelle, "taux_abandon_primaire": "", "eleves_primaire": "",
                       "taux_abandon_filles": "", "taux_abandon_garcons": "",
                       f"repere_taux_{annee}": round(float(d["abandon_primaire_precedent"]), 2),
                       f"repere_eleves_{annee}": int(d["eleves_primaire"])})
    return pd.DataFrame(lignes).to_csv(sep=";", index=False)


def lire_csv(texte: str) -> list[dict]:
    t = pd.read_csv(io.StringIO(texte.lstrip("﻿")), sep=None, engine="python", dtype=str)
    t.columns = [c.strip() for c in t.columns]
    for c in ["taux_abandon_primaire", "eleves_primaire", "taux_abandon_filles", "taux_abandon_garcons"]:
        if c in t.columns:
            t[c] = pd.to_numeric(t[c].str.replace(",", ".").str.replace(" ", "").str.replace(" ", ""), errors="coerce")
    garder = [c for c in COLONNES if c in t.columns]
    return t[garder].replace({np.nan: None}).to_dict("records")


def _classe(v: float, seuils: dict) -> str:
    return "élevé" if v >= seuils["eleve"] else ("moyen" if v >= seuils["moyen"] else "faible")


def _taux_prevus(g: pd.DataFrame, prevision: dict) -> list[float]:
    """Taux prévus à 1, 2 et 3 ans par le modèle retenu, à partir de l'historique de la province."""
    niveau = _niveau(g)
    if prevision["modele_retenu"] != "retour_amorti":
        return [niveau] * 3
    dernier = g.sort_values("annee_scolaire").iloc[-1]
    actuel = dernier["abandon_primaire_precedent"]
    rupture = abs(float(dernier["evolution_eleves_primaire"])) > SEUIL_RUPTURE if pd.notna(dernier["evolution_eleves_primaire"]) else False
    ecart = 0.0 if (pd.isna(actuel) or rupture) else logit(max(float(actuel), 0.0)) - logit(niveau)
    phi = float(prevision["reglages"]["phi"])
    return [taux(logit(niveau) + phi ** h * ecart) for h in [1, 2, 3]]


def _previsions(valeurs: list[float], marges: dict, annee: str, seuils: dict) -> list[dict]:
    sortie, a = [], annee
    for h, v in zip([1, 2, 3], valeurs):
        a = annee_suivante(a)
        z, m = logit(v), float(marges[str(h)])
        sortie.append({"annee": a, "taux": round(v, 2), "bas": round(taux(z - m), 2), "haut": round(taux(z + m), 2),
                       "classe": _classe(v, seuils)})
    return sortie


def _score_rupture(lignes_province: pd.DataFrame) -> float:
    alerte = D.modeles["ensemble"]["alerte_rupture"]
    g = lignes_province.sort_values("annee_scolaire")
    flags = (g["evolution_eleves_primaire"].abs() > SEUIL_RUPTURE).astype(float)
    dernier = g.iloc[-1]
    x = {"evolution_eleves_primaire": dernier["evolution_eleves_primaire"],
         "baisse_effectifs": max(-float(dernier["evolution_eleves_primaire"]), 0.0),
         "rupture_annee_precedente": float(flags.iloc[-1]), "ruptures_passees": float(flags.sum()),
         "abandon_primaire_precedent": dernier["abandon_primaire_precedent"],
         "abandons_primaire_orpaillage_pour_1000_region": dernier["abandons_primaire_orpaillage_pour_1000_region"],
         "hors_ecole_16_18_province": dernier["hors_ecole_16_18_province"]}
    n = alerte["normalisation"]
    v = pd.Series(x)[alerte["variables"]].astype(float).fillna(pd.Series(n["mediane"]))
    z = (v - pd.Series(n["moyenne"])) / pd.Series(n["ecart_type"])
    return float(alerte["modele"].predict_proba(pd.DataFrame([z.values], columns=alerte["variables"]))[0, 1])


def controler(lignes: list[dict], annee: str) -> tuple[pd.DataFrame, list[dict]]:
    """Contrôles avant calcul : provinces connues et complètes, valeurs plausibles, ruptures probables."""
    messages = []
    t = pd.DataFrame(lignes)
    for c in COLONNES:
        if c not in t.columns:
            t[c] = None
    t["province_pcode"] = t["province_pcode"].astype(str).str.strip()
    connues = set(D.tableau_ensemble["province_pcode"])
    inconnues = sorted(set(t["province_pcode"]) - connues)
    if inconnues:
        messages.append({"niveau": "erreur", "texte": f"Codes de province inconnus : {', '.join(inconnues)}"})
    t = t[t["province_pcode"].isin(connues)].drop_duplicates("province_pcode", keep="last")
    for c in ["taux_abandon_primaire", "eleves_primaire", "taux_abandon_filles", "taux_abandon_garcons"]:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    complet = t["taux_abandon_primaire"].notna() & t["eleves_primaire"].notna()
    manquantes = sorted(connues - set(t.loc[complet, "province_pcode"]))
    if manquantes:
        noms = D.tableau_ensemble.set_index("province_pcode").loc[manquantes, "province_nom"]
        messages.append({"niveau": "attention", "texte": f"{len(manquantes)} provinces sans taux ou sans effectif : elles gardent leur prévision actuelle "
                                                         f"({', '.join(noms.head(8))}{'…' if len(noms) > 8 else ''})."})
    t = t[complet]
    hors = t[(t["taux_abandon_primaire"] < -5) | (t["taux_abandon_primaire"] > 100)]
    if len(hors):
        messages.append({"niveau": "erreur", "texte": f"Taux hors de l'intervalle plausible pour : {', '.join(hors['province_pcode'])}"})
        t = t.drop(hors.index)
    nuls = t[t["eleves_primaire"] <= 0]
    if len(nuls):
        messages.append({"niveau": "erreur", "texte": f"Effectif nul ou négatif pour : {', '.join(nuls['province_pcode'])}"})
        t = t.drop(nuls.index)
    t["annee_scolaire"] = annee
    return t, messages


def calculer(lignes: list[dict]) -> dict:
    """Aperçu : nouvelles prévisions de chaque province, sans rien enregistrer."""
    annee = annee_suivante(derniere_annee())
    t, messages = controler(lignes, annee)
    h = historique()
    hs = historique_sexe()
    fiche = D.fiche("ensemble")["prevision"]
    fiche_sexe = D.fiche("F")["prevision"]
    noms = D.tableau_ensemble.set_index("province_pcode")
    resultats = []
    saisies = t.set_index("province_pcode")
    for pcode, g in h.groupby("province_pcode"):
        avant_niveau = _taux_prevus(g, fiche)[0]
        avant_score = _score_rupture(g)
        ligne = {"pcode": pcode, "province": noms.loc[pcode, "province_nom"], "region": noms.loc[pcode, "region_nom"],
                 "saisie": pcode in saisies.index, "avant": round(avant_niveau, 2), "classe_avant": _classe(avant_niveau, fiche["seuils_classes_taux"]),
                 "score_avant": round(avant_score, 3)}
        if pcode in saisies.index:
            s = saisies.loc[pcode]
            dernier = g.iloc[-1]
            evolution = float(s["eleves_primaire"]) / max(float(dernier["eleves_primaire"]), 1) - 1
            nouvelle = {**dernier.to_dict(), "annee_scolaire": annee, "abandon_primaire_precedent": float(s["taux_abandon_primaire"]),
                        "eleves_primaire": float(s["eleves_primaire"]), "evolution_eleves_primaire": evolution}
            g2 = pd.concat([g, pd.DataFrame([nouvelle])], ignore_index=True)
            ligne.update({"taux_saisi": float(s["taux_abandon_primaire"]), "evolution_effectifs": round(evolution, 4),
                          "rupture_annee": abs(evolution) > SEUIL_RUPTURE})
        else:
            g2 = g
        ligne["previsions"] = _previsions(_taux_prevus(g2, fiche), fiche["marge_conforme_logit_par_horizon"], annee,
                                          fiche["seuils_classes_taux"])
        ligne["score_rupture"] = round(_score_rupture(g2), 3)
        seuils_alerte = D.modeles["ensemble"]["fiche"]["alerte_rupture"]["seuils_score"]
        ligne["risque_rupture"] = "élevé" if ligne["score_rupture"] >= seuils_alerte[1] else ("moyen" if ligne["score_rupture"] >= seuils_alerte[0] else "faible")
        for sexe, col in [("F", "taux_abandon_filles"), ("G", "taux_abandon_garcons")]:
            gs = hs[(hs["province_pcode"] == pcode) & (hs["sexe"] == sexe)]
            if len(gs) and pcode in saisies.index and pd.notna(saisies.loc[pcode, col]):
                gs = pd.concat([gs, pd.DataFrame([{"abandon_primaire_precedent": float(saisies.loc[pcode, col]),
                                                   "evolution_eleves_primaire": ligne["evolution_effectifs"]}])])
            if len(gs):
                gs = gs.assign(annee_scolaire=gs["annee_scolaire"].fillna(annee))
                ligne["filles" if sexe == "F" else "garcons"] = round(_taux_prevus(gs, fiche_sexe)[0], 2)
        resultats.append(ligne)
    resultats.sort(key=lambda r: -r["previsions"][0]["taux"])
    changements = [r for r in resultats if r["previsions"][0]["classe"] != r["classe_avant"]]
    ruptures = [r for r in resultats if r.get("rupture_annee")]
    return {"annee": annee, "annees_prevues": [p["annee"] for p in resultats[0]["previsions"]], "messages": messages,
            "provinces_saisies": int(t.shape[0]), "resultats": resultats,
            "resume": {"changements_de_classe": len(changements), "ruptures_detectees": len(ruptures),
                       "alertes_elevees": sum(r["risque_rupture"] == "élevé" for r in resultats),
                       "eleve": sum(r["previsions"][0]["classe"] == "élevé" for r in resultats),
                       "moyen": sum(r["previsions"][0]["classe"] == "moyen" for r in resultats),
                       "faible": sum(r["previsions"][0]["classe"] == "faible" for r in resultats)},
            "lignes_valides": t.replace({np.nan: None}).to_dict("records")}


def enregistrer(lignes: list[dict]) -> dict:
    apercu = calculer(lignes)
    if any(m["niveau"] == "erreur" for m in apercu["messages"]):
        return {"enregistre": False, "messages": apercu["messages"]}
    if not apercu["provinces_saisies"]:
        return {"enregistre": False, "messages": [{"niveau": "erreur", "texte": "Aucune province complète à enregistrer."}]}
    DOSSIER.mkdir(parents=True, exist_ok=True)
    annee = apercu["annee"]
    pd.DataFrame(apercu["lignes_valides"])[COLONNES].to_csv(DOSSIER / f"{annee}.csv", sep=";", index=False, encoding="utf-8-sig")
    previsions_csv(apercu).to_csv(DOSSIER / f"previsions_{annee}.csv", sep=";", index=False, encoding="utf-8-sig")
    return {"enregistre": True, "annee": annee, "messages": apercu["messages"]}


def previsions_csv(apercu: dict) -> pd.DataFrame:
    lignes = []
    for r in apercu["resultats"]:
        ligne = {"province_pcode": r["pcode"], "province_nom": r["province"], "region_nom": r["region"],
                 "donnees_saisies": r["saisie"], "score_rupture": r["score_rupture"], "risque_de_rupture": r["risque_rupture"]}
        for p in r["previsions"]:
            ligne[f"taux_prevu_{p['annee']}"] = p["taux"]
            ligne[f"borne_basse_80_{p['annee']}"] = p["bas"]
            ligne[f"borne_haute_80_{p['annee']}"] = p["haut"]
            ligne[f"classe_{p['annee']}"] = p["classe"]
        lignes.append(ligne)
    return pd.DataFrame(lignes)


def annuler(annee: str) -> bool:
    """Retire la dernière année saisie (et seulement elle)."""
    if not mises_a_jour() or mises_a_jour()[-1] != annee:
        return False
    for nom in [f"{annee}.csv", f"previsions_{annee}.csv"]:
        (DOSSIER / nom).unlink(missing_ok=True)
    return True
