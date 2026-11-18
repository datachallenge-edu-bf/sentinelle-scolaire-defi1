"""Chemins et paramètres communs à toute la chaîne de traitement."""

from __future__ import annotations

import os
from pathlib import Path

# Racine du projet du défi 1 (dossier defi1_sentinelle).
RACINE = Path(__file__).resolve().parents[2]

# Données remises par les organisateurs : lecture seule. Elles sont rangées dans le dossier qui
# contient le projet ; la variable d'environnement SENTINELLE_DONNEES permet d'en indiquer un autre.
DOSSIER_ORGANISATEURS = Path(os.environ.get("SENTINELLE_DONNEES", RACINE.parent)).resolve()
DATA_PACK = DOSSIER_ORGANISATEURS / "DataPack_DCB_2026"
PACK_CSV = DATA_PACK / "data"
# Sources publiques ajoutées par les équipes (hors Data Pack) : PDF d'origine, CSV au format du pack, manifeste.
SOURCES_EXTERNES = DOSSIER_ORGANISATEURS / "sources_externes"
EXTERNES_CSV = SOURCES_EXTERNES / "data"
MANIFESTE_EXTERNE = SOURCES_EXTERNES / "manifeste_sources_externes.csv"
PREFIXE_EXTERNE = "externe:"
# Extraction indépendante du RGPH 2019 (volume 3) par un membre de l'équipe : sert de contrôle.
CONTROLE_PAUVRETE = DOSSIER_ORGANISATEURS / "Sentinelle_Scolaire_Pauvrete_INSD_2019.xlsx"
# Projections de population actualisées de l'INSD (portail OpenDataForAfrica), classeurs Excel téléchargés.
DONNEES_POPULATION = DOSSIER_ORGANISATEURS / "Data_Population"
MANIFESTE = DATA_PACK / "00_Documentation_et_Referentiels" / "manifeste_telechargements.csv"
BASE_PRINCIPALE = DOSSIER_ORGANISATEURS / "DONNEES_STATISTQUES_ PRESCOLAIRE ET PRIMAIRE_2016_2025_DCB.xlsx"
DOCUMENT_CHALLENGE = DOSSIER_ORGANISATEURS / "Document_du_challenge_Data_Challenge_Burkina.pdf"
# Les trois éléments remis par les organisateurs sont protégés ; les projets rangés à côté ne le sont pas.
FICHIERS_ORGANISATEURS = (DATA_PACK, BASE_PRINCIPALE, DOCUMENT_CHALLENGE)

CONTOURS_CODAB = (
    DATA_PACK / "04_Cartographie_SIG" / "COD-AB_limites_administratives" / "bfa_admin_boundaries.geojson.zip"
)

# Sorties de la chaîne.
DONNEES = RACINE / "data"
SORTIE_COLLECTE = DONNEES / "01_collecte"
SORTIE_NETTOYAGE = DONNEES / "02_nettoyage"
BASE_GEOPACKAGE = SORTIE_NETTOYAGE / "sentinelle_scolaire.gpkg"
CONTOURS_WEB = SORTIE_NETTOYAGE / "contours_web"
FIGURES = RACINE / "outputs" / "figures"
DEPOTS = RACINE / "depots"

# Système de coordonnées : WGS 84 pour le stockage, UTM 30N pour les surfaces et distances.
CRS_STOCKAGE = "EPSG:4326"
CRS_METRIQUE = "EPSG:32630"

# Convention de nommage des dépôts : EQUIPE_ETAPE_DEFI_ROLE_description_vN.
# Préfixe des noms de dépôt. L'évaluation est à l'aveugle (aucun nom d'équipe ni de membre dans les fichiers) :
# le préfixe est le nom de la solution.
EQUIPE = os.environ.get("SENTINELLE_EQUIPE", "SENTINELLE")
DEFI = "D1"

# Format des fichiers produits : séparateur du Data Pack, encodage lisible par Excel.
SEPARATEUR = ";"
ENCODAGE_SORTIE = "utf-8-sig"


def fichiers_organisateurs() -> list[Path]:
    """Liste de tous les fichiers remis par les organisateurs."""
    fichiers: list[Path] = []
    for element in FICHIERS_ORGANISATEURS:
        if element.is_dir():
            fichiers.extend(p for p in element.rglob("*") if p.is_file())
        elif element.is_file():
            fichiers.append(element)
    return sorted(fichiers)


def verifier_ecriture(chemin: Path) -> Path:
    """Refuse toute écriture sur les fichiers remis par les organisateurs."""
    chemin = Path(chemin).resolve()
    for protege in FICHIERS_ORGANISATEURS:
        protege = protege.resolve()
        if chemin == protege or chemin.is_relative_to(protege):
            raise PermissionError(f"Écriture interdite dans les données des organisateurs : {chemin}")
    return chemin
