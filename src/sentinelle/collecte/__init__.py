"""Étape 01 : collecte des données."""

from .catalogue import CATALOGUE, NOMS_DEPOT, SOURCES_ECARTEES, Jeu, Regle, jeu
from .extraction import (
    bilan_sources,
    controle_couverture,
    executer_collecte,
    extraire_base_principale,
    extraire_jeu,
    inventaire_fichiers,
    selectionner_pages,
)

__all__ = [
    "CATALOGUE",
    "NOMS_DEPOT",
    "SOURCES_ECARTEES",
    "Jeu",
    "Regle",
    "jeu",
    "bilan_sources",
    "controle_couverture",
    "executer_collecte",
    "extraire_base_principale",
    "extraire_jeu",
    "inventaire_fichiers",
    "selectionner_pages",
]
