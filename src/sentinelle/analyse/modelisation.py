"""Modèle du décrochage au primaire, en trois briques (ensemble des élèves et par sexe) :

1. ``prevision`` : taux d'abandon prévu à 1, 2 et 3 ans, intervalle à 80 % calibré ;
2. ``explication`` : pourquoi le niveau habituel d'une province est élevé ;
3. ``alerte`` : risque de rupture de scolarisation (ensemble seulement : une école ferme pour
   les filles comme pour les garçons).

La table ``tableau_de_bord_<jeu>`` réunit, pour 2025-2026, la prévision, sa classe de risque,
les facteurs explicatifs et l'alerte de rupture de chaque province.
"""

from __future__ import annotations

import pandas as pd

from . import alerte, explication, prevision
from . import preparation as P

HORIZONS = [1, 2, 3]


def modeliser(jeu: dict, nom: str, listes: pd.DataFrame) -> dict[str, pd.DataFrame]:
    entite = jeu["entite"]
    d, lineaire, arbres = P.preparer(jeu, nom, listes)
    resultats, evaluations, couvertures, previsions, frequences = {}, [], [], [], []
    reglages = modele = t1 = None
    for h in HORIZONS:
        t = P.avec_cible(d, jeu, nom, h)
        if h == 1:
            reglages, info = prevision.choisir_reglages(t, lineaire, arbres, nom)
            resultats[f"grille_reglages_{nom}"] = info["grille"]
            t1 = t
        evaluation, prev, choix_plis = prevision.evaluer(t, lineaire, arbres, reglages, entite, nom, h)
        if evaluation.empty:
            continue
        evaluations.append(evaluation)
        if h == 1:
            modele = prevision.choisir_modele(evaluation)
        # Variables du modèle final : retenues dans au moins la moitié des plis.
        choix = {}
        for m in ["elastic_net", "ridge_effet_province", "lightgbm"]:
            stables, frequence = prevision.variables_stables(choix_plis, m)
            choix[m] = stables or choix_plis[-1][m]
            frequences.append(frequence.assign(horizon=h))
        selection, finale = prev[prev["role"] == "sélection"], prev[prev["role"] == "test final"]
        marge = prevision.marge_conforme(selection if len(selection) else prev, modele)
        if len(finale):
            couvertures.append(prevision.couverture(finale, modele, marge, h))
        annees_x = [P.DERNIERE_ANNEE] + (["2023-2024"] if nom == "sexe" and h == 1 else [])
        sortie, seuils = prevision.prevoir(d, t, nom, choix, reglages, modele,
                                           prevision.marge_conforme(prev, modele), h, annees_x)
        previsions.append(sortie)
        if h == 1:
            resultats[f"seuils_classes_{nom}"] = pd.DataFrame(
                {"classe": ["moyen à partir de (médiane)", "élevé à partir de (80e centile)"],
                 "taux_abandon_prevu": seuils.round(2)})
    evaluation = pd.concat(evaluations, ignore_index=True)
    resultats[f"evaluation_plis_{nom}"] = evaluation.round(4)
    resultats[f"synthese_modeles_{nom}"] = prevision.synthese(evaluation)
    resultats[f"intervalle_{nom}"] = pd.DataFrame(couvertures)
    resultats[f"reglages_{nom}"] = pd.DataFrame([{**reglages, "modele_retenu": modele}])
    resultats[f"variables_retenues_{nom}"] = pd.concat(frequences, ignore_index=True)
    resultats[f"previsions_{nom}"] = pd.concat(previsions, ignore_index=True)

    for cle, table in explication.executer(d, t1, entite, arbres).items():
        resultats[f"explication_{cle}_{nom}"] = table
    if nom == "ensemble":
        resultats.update(alerte.executer(d, t1))
    return resultats


def tableau_de_bord(resultats: dict[str, pd.DataFrame], nom: str) -> pd.DataFrame:
    """Prévision 2025-2026, projections à 2 et 3 ans, facteurs explicatifs et alerte de rupture."""
    prev = resultats[f"previsions_{nom}"]
    entite = ["province_pcode"] + (["sexe"] if nom == "sexe" else [])
    annee = P.annee_plus(P.DERNIERE_ANNEE, 1)
    t = prev[(prev["horizon"] == 1) & (prev["annee_prevue"] == annee)].drop(columns=["horizon"])
    plus_loin = prev[prev["horizon"] > 1].pivot_table(index=entite, columns="annee_prevue", values="taux_abandon_prevu")
    plus_loin.columns = [f"taux_abandon_prevu_{c}" for c in plus_loin.columns]
    facteurs = resultats[f"explication_facteurs_{nom}"].drop(columns=["province_nom", "region_nom"])
    t = t.merge(plus_loin.reset_index(), on=entite, how="left").merge(facteurs, on=entite, how="left")
    rupture = resultats["alerte_rupture"][["province_pcode", "score_rupture", "risque_de_rupture"]]
    return t.merge(rupture, on="province_pcode", how="left").sort_values(
        "taux_abandon_prevu", ascending=False).reset_index(drop=True)
