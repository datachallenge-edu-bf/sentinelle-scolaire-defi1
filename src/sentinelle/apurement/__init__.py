"""Apurement du panel provincial de 2025 : une base sans cellule vide, dont chaque valeur est tracée.

Entrée : ``data/03_transformation/panel_province_2025.csv`` (47 provinces × 9 années scolaires).
Sortie : ``data/03_transformation/base_apuree/``.

Quatre temps :

0. sélection des 79 colonnes de la base apurée (module ``selection``) ;
1. recodage des valeurs impossibles puis imputation par variable, méthode choisie par test
   (module ``imputation``) ;
2. valeurs publiées par l'INSD pour le post-primaire, retenues après contrôle contre le panel
   (module ``sources_insd``) ;
3. complétion des cellules restantes (module ``completion``) ;
4. base par sexe : les variables publiées par sexe, ancrées sur l'ensemble de la base apurée
   (module ``par_sexe``).

Chaque cellule reçoit un statut : observée, valeur publiée INSD, imputée (étapes 1 et 2) ou
complétée à l'étape 3. Ce statut permet d'écarter de l'apprentissage d'un modèle toute cible
qui n'a pas été observée.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config
from . import classeur, completion, imputation, par_sexe, selection, sources_insd
from .etat import COMPLETEE, IMPUTEE, OBSERVEE, SOURCE_INSD, Apurement

ENTREE = config.DONNEES / "03_transformation" / "panel_province_2025.csv"
SORTIE = config.DONNEES / "03_transformation" / "base_apuree"
SOURCES_INSD = config.DONNEES / "sources_transcrites" / "insd_post_primaire_province.csv"


def statut_cellules(etat: Apurement) -> pd.DataFrame:
    """Une ligne par cellule de variable : statut et dernière méthode appliquée."""
    d = etat.base
    methode = {}
    for ligne in etat.journal:
        if ligne["nature"] != "recodage":
            methode[(ligne["_i"], ligne["variable"])] = (ligne["etape"], ligne["methode"])
    recodees = {(ligne["_i"], ligne["variable"]) for ligne in etat.journal if ligne["nature"] == "recodage"}
    lignes = []
    for i in d.index:
        for variable in selection.VARIABLES:
            etape, nom = methode.get((i, variable), ("", ""))
            lignes.append({"province_pcode": d.at[i, "province_pcode"], "province_nom": d.at[i, "province_nom"],
                           "annee_scolaire": d.at[i, "annee_scolaire"], "variable": variable,
                           "statut": etat.statut.get((i, variable), OBSERVEE),
                           "recodee_avant_imputation": (i, variable) in recodees, "etape": etape, "methode": nom})
    return pd.DataFrame(lignes)


def controler(etat: Apurement, panel: pd.DataFrame, statuts: pd.DataFrame, e2) -> pd.DataFrame:
    d = etat.base
    observees = statuts[statuts["statut"] == OBSERVEE]
    depart = panel.set_index(["province_pcode", "annee_scolaire"])
    arrivee = d.set_index(["province_pcode", "annee_scolaire"])
    ecarts = 0
    for r in observees.itertuples():
        a, b = depart.at[(r.province_pcode, r.annee_scolaire), r.variable], arrivee.at[(r.province_pcode, r.annee_scolaire), r.variable]
        if r.recodee_avant_imputation:
            continue
        if isinstance(b, (int, float, np.floating, np.integer)) and not isinstance(b, bool):
            ecarts += int(not (pd.isna(a) and pd.isna(b)) and not abs(float(a) - float(b)) < 1e-9)
        else:
            ecarts += int(str(a) != str(b))
    flux = d[["abandon_primaire_precedent", "redoublement_primaire_precedent", "promotion_primaire_precedente"]]
    somme = (flux.sum(axis=1) - 100).abs()
    proportions = [c for c in selection.VARIABLES if c.startswith("part_") and d[c].max() <= 1.0001]
    statut = statuts["statut"].value_counts()
    resultats = [
        ("aucune_cellule_vide", int(d[selection.VARIABLES].isna().sum().sum()) == 0,
         f"{len(d)} lignes × {len(selection.VARIABLES)} variables, {int(d[selection.VARIABLES].isna().sum().sum())} "
         f"cellule(s) vide(s)"),
        ("valeurs_observees_inchangees", ecarts == 0,
         f"{len(observees)} cellules observées comparées au panel de l'étape 03 : {ecarts} écart(s)"),
        ("flux_somme_100", bool((somme <= 0.05).mean() >= 0.99),
         f"abandon + redoublement + promotion = 100 à 0,05 près pour {int((somme <= 0.05).sum())} lignes sur {len(d)}"),
        ("proportions_entre_0_et_1", bool(((d[proportions] >= 0) & (d[proportions] <= 1.0001)).all().all()),
         f"{len(proportions)} variables de proportion"),
        ("sources_insd_controlees", len(e2.retenues) > 0,
         f"{len(e2.retenues)} valeurs INSD retenues, {len(e2.rejetees)} rejetées au contrôle"),
        ("statut_de_chaque_cellule", len(statuts) == len(d) * len(selection.VARIABLES),
         ", ".join(f"{k} {v}" for k, v in statut.items())),
    ]
    return pd.DataFrame(resultats, columns=["controle", "conforme", "detail"])


def executer_apurement() -> dict[str, pd.DataFrame]:
    sortie = config.verifier_ecriture(SORTIE)
    sortie.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(ENTREE, sep=config.SEPARATEUR, encoding=config.ENCODAGE_SORTIE)
    base, retirees = selection.selectionner(panel)
    etat = Apurement(base)
    e1 = imputation.executer(etat)
    e2 = sources_insd.executer(etat, e1.avant, SOURCES_INSD)
    e3 = completion.executer(etat, e2.sources)
    d = etat.base
    d["nb_valeurs_imputees"] = [etat.imputations_par_ligne.get(i, 0) for i in d.index]
    d["statut_imputation"] = [etat.statut_ligne[i] for i in d.index]
    statuts = statut_cellules(etat)
    controles = controler(etat, panel, statuts, e2)
    tables = {"base_apuree": d, "statut_cellules": statuts, "journal_apurement": etat.journal_table(),
              "variables_retirees": retirees, "controles_apurement": controles,
              "sources_insd_retenues": pd.DataFrame(e2.retenues), "sources_insd_rejetees": pd.DataFrame(e2.rejetees),
              "sources_insd_controle": pd.DataFrame(e2.controles)}
    for nom, table in tables.items():
        table.to_csv(sortie / f"{nom}.csv", sep=config.SEPARATEUR, encoding=config.ENCODAGE_SORTIE, index=False)
    classeur.ecrire(etat, e1, e2, e3, tables, sortie / "base_defi1_apuree.xlsx")
    tables.update(par_sexe.executer(d, statuts, sortie))
    return tables


__all__ = ["executer_apurement", "OBSERVEE", "SOURCE_INSD", "IMPUTEE", "COMPLETEE"]
