"""Étape 04 : analyse.

Entrée : ``data/03_transformation/base_apuree/`` (base apurée et base par sexe).
Sortie : ``data/04_analyse/``.

- ``exploration`` : la cible, sa variance, la qualité, la colinéarité et le lien de chaque
  variable avec la cible, et la décision motivée de garder ou de retirer chaque variable ;
- ``modelisation`` : modèle du décrochage (ensemble et par sexe), validation dans le temps,
  intervalle calibré, explication de chaque prévision, alerte de rupture.
"""

from __future__ import annotations

import pandas as pd

from .. import config
from . import exploration, modelisation

ENTREE = config.DONNEES / "03_transformation" / "base_apuree"
SORTIE = config.DONNEES / "04_analyse" / "exploration"
SORTIE_MODELISATION = config.DONNEES / "04_analyse" / "modelisation"


def executer_exploration() -> dict[str, pd.DataFrame]:
    sortie = config.verifier_ecriture(SORTIE)
    sortie.mkdir(parents=True, exist_ok=True)
    jeux = exploration.charger(ENTREE)
    tables = {}
    for nom, jeu in jeux.items():
        tables.update(exploration.analyser(jeu, nom))
    for nom, table in tables.items():
        table.to_csv(sortie / f"{nom}.csv", sep=config.SEPARATEUR, encoding=config.ENCODAGE_SORTIE, index=False)
    return tables


def executer_modelisation() -> dict[str, pd.DataFrame]:
    """Modèle du décrochage, ensemble et par sexe ; les listes de variables viennent de l'exploration."""
    sortie = config.verifier_ecriture(SORTIE_MODELISATION)
    sortie.mkdir(parents=True, exist_ok=True)
    jeux = exploration.charger(ENTREE)
    tables = {}
    for nom, jeu in jeux.items():
        listes = pd.read_csv(SORTIE / f"variables_modele_{nom}.csv", sep=config.SEPARATEUR,
                             encoding=config.ENCODAGE_SORTIE)
        tables.update(modelisation.modeliser(jeu, nom, listes))
    for nom in jeux:
        tables[f"tableau_de_bord_{nom}"] = modelisation.tableau_de_bord(tables, nom)
    for nom, table in tables.items():
        table.to_csv(sortie / f"{nom}.csv", sep=config.SEPARATEUR, encoding=config.ENCODAGE_SORTIE, index=False)
    return tables


__all__ = ["executer_exploration", "executer_modelisation"]
