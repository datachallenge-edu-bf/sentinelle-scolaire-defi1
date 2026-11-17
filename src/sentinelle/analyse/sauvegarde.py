"""Sauvegarde et rechargement des modèles retenus, pour le déploiement.

Pour chaque jeu (``ensemble``, ``sexe``), le dossier ``data/04_analyse/modeles/<jeu>/`` contient :

- ``fiche_modele.json`` : modèle de prévision retenu, marges conformes par horizon (échelle logit),
  seuils des classes de risque, réglages, variables retenues de chaque modèle, qualité mesurée ;
- ``explication_lightgbm.joblib`` et ``explication_lightgbm.txt`` : facteurs par province ;
- ``explication_elastic_net.joblib`` : effets chiffrés, avec ses paramètres de normalisation ;
- ``alerte_rupture.joblib`` (ensemble seulement) : score de rupture et sa normalisation.

Le format texte de LightGBM se relit sans Python (``lightgbm.Booster(model_file=...)``).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import joblib
import lightgbm
import numpy as np
import pandas as pd
import shap
import sklearn


def _json(valeur):
    if isinstance(valeur, dict):
        return {str(k): _json(v) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [_json(v) for v in valeur]
    if isinstance(valeur, (np.floating, float)):
        return None if np.isnan(valeur) else float(valeur)
    if isinstance(valeur, (np.integer,)):
        return int(valeur)
    return valeur


def sauvegarder(objets: dict, resultats: dict[str, pd.DataFrame], nom: str, dossier: Path) -> Path:
    cible = dossier / nom
    cible.mkdir(parents=True, exist_ok=True)
    expl = objets["explication"]
    joblib.dump({"modele": expl["lightgbm"], "variables": expl["variables_lightgbm"]},
                cible / "explication_lightgbm.joblib")
    expl["lightgbm"].booster_.save_model(str(cible / "explication_lightgbm.txt"))
    joblib.dump({"modele": expl["elastic_net"], "variables": expl["variables_elastic_net"],
                 "normalisation": expl["normalisation_elastic_net"]}, cible / "explication_elastic_net.joblib")
    if "alerte" in objets:
        joblib.dump(objets["alerte"], cible / "alerte_rupture.joblib")

    prev = objets["prevision"]
    synthese = resultats[f"synthese_modeles_{nom}"]
    retenu = synthese[(synthese["modele"] == prev["modele"]) & (synthese["horizon"] == 1)]
    fiche = {
        "jeu": nom,
        "date": date.today().isoformat(),
        "cible": "taux d'abandon du primaire (%) entre t+h-1 et t+h, par province"
                 + (" et par sexe" if nom == "sexe" else ""),
        "normalisation_cible": "z = logit(taux / 100), taux ramené dans [0,5 ; 99,5] ; dénormalisation : "
                               "taux = 100 / (1 + exp(-z))",
        "prevision": {
            "modele_retenu": prev["modele"],
            "regle_de_choix": "niveau habituel à battre : gain d'au moins 3 % d'erreur et au moins 2 plis sur 3 ; à défaut, modèle suivant la situation de l'année (retour amorti, combinaison) s'il est aussi précis à 1 % près sur les plis de sélection",
            "marge_conforme_logit_par_horizon": prev["marges"],
            "niveau_intervalle": 0.80,
            "seuils_classes_taux": {"moyen": prev["seuils"][0], "eleve": prev["seuils"][1]},
            "reglages": prev["reglages"],
            "variables_par_modele": prev["variables"],
            "qualite_horizon_1": retenu[["role", "erreur_absolue_moyenne", "correlation_rang",
                                         "rappel_quintile_le_plus_a_risque"]].to_dict("records"),
            "couverture_intervalle": resultats[f"intervalle_{nom}"].to_dict("records"),
        },
        "explication": {
            "effets_chiffres": {"modele": "elastic_net", "variables": expl["variables_elastic_net"],
                                "r2_provinces_non_vues": expl["r2_elastic_net"]},
            "facteurs_par_province": {"modele": "lightgbm (élimination récursive guidée par SHAP)",
                                      "variables": expl["variables_lightgbm"],
                                      "r2_provinces_non_vues": expl["r2_lightgbm"]},
        },
        "versions": {"lightgbm": lightgbm.__version__, "scikit-learn": sklearn.__version__,
                     "shap": shap.__version__, "pandas": pd.__version__},
    }
    if "alerte" in objets:
        fiche["alerte_rupture"] = {"modele": "régression logistique pénalisée, classes équilibrées",
                                   "variables": objets["alerte"]["variables"],
                                   "seuils_score": list(objets["alerte"]["seuils"]),
                                   "evaluation": resultats["evaluation_alerte_rupture"].to_dict("records")}
    (cible / "fiche_modele.json").write_text(json.dumps(_json(fiche), ensure_ascii=False, indent=2), encoding="utf-8")
    return cible


def charger(dossier: Path, nom: str) -> dict:
    """Modèles et fiche d'un jeu, pour l'API."""
    cible = Path(dossier) / nom
    modeles = {"fiche": json.loads((cible / "fiche_modele.json").read_text(encoding="utf-8")),
               "explication_lightgbm": joblib.load(cible / "explication_lightgbm.joblib"),
               "explication_elastic_net": joblib.load(cible / "explication_elastic_net.joblib")}
    if (cible / "alerte_rupture.joblib").exists():
        modeles["alerte_rupture"] = joblib.load(cible / "alerte_rupture.joblib")
    return modeles
