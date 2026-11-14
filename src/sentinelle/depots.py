"""Préparation des dépôts selon la convention du challenge.

Modèle : EQUIPE_ETAPE_DEFI_ROLE_description_vN.extension
Exemple : E07_02-nettoyage_D1_engineer_effectifs-primaire-propres_v2.csv
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path

import pandas as pd

from . import config
from .collecte.catalogue import NOMS_DEPOT

ETAPES = {
    1: "01-collecte",
    2: "02-nettoyage",
    3: "03-transformation",
    4: "04-analyse",
    5: "05-interpretation",
}
ROLES = {"engineer", "architect", "analyst", "scientist"}


def slug(texte: str) -> str:
    """Texte sans accent ni espace, en minuscules, mots séparés par des tirets."""
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sans_accent.lower()).strip("-")


def nom_depot(etape: int, role: str, description: str, version: int = 1, extension: str = "csv") -> str:
    if etape not in ETAPES:
        raise ValueError(f"Étape inconnue : {etape}")
    if role not in ROLES:
        raise ValueError(f"Rôle inconnu : {role}")
    return f"{config.EQUIPE}_{ETAPES[etape]}_{config.DEFI}_{role}_{slug(description)}_v{version}.{extension}"


def deposer(etape: int, fichiers: list[tuple[Path, str, str, str]], entete: list[str],
            version: int = 1) -> pd.DataFrame:
    """Copie des fichiers dans depots/<étape> sous leur nom normalisé et écrit le LISEZ-MOI.

    ``fichiers`` : liste de (chemin produit, rôle, description pour le nom, contenu pour le LISEZ-MOI).
    Le dossier de l'étape est vidé au préalable pour qu'aucun fichier périmé ne subsiste.
    """
    cible = config.verifier_ecriture(config.DEPOTS / ETAPES[etape])
    cible.mkdir(parents=True, exist_ok=True)
    # Le contenu est vidé sans supprimer le dossier lui-même, que Windows peut garder ouvert.
    for element in cible.iterdir():
        if element.is_dir():
            shutil.rmtree(element)
        else:
            element.unlink()

    lignes = []
    for chemin, role, description, contenu in fichiers:
        if not chemin.exists():
            continue
        nom = nom_depot(etape, role, description, version, chemin.suffix.lstrip("."))
        shutil.copy2(chemin, cible / nom)
        lignes.append({"fichier_depose": nom, "role": role,
                       "fichier_produit": chemin.relative_to(config.RACINE).as_posix(), "contenu": contenu})
    table = pd.DataFrame(lignes)

    roles = sorted(set(table["role"])) if not table.empty else ["engineer"]
    role_lisez_moi = roles[0] if len(roles) == 1 else "engineer"
    corps = [f"{r.fichier_depose}\n    {r.contenu}" for r in table.itertuples()]
    (cible / nom_depot(etape, role_lisez_moi, "lisez-moi", version, "txt")).write_text(
        "\n".join(entete + ["", "FICHIERS", ""] + corps) + "\n", encoding="utf-8")
    return table


def exporter_collecte(version: int = 1, role: str = "engineer") -> pd.DataFrame:
    """Dépôt de l'étape 01 : extractions brutes, registre, bilan, inventaire, contrôle de couverture."""
    source = config.SORTIE_COLLECTE
    registre = pd.read_csv(source / "registre_sources.csv", sep=config.SEPARATEUR,
                           dtype=str, encoding=config.ENCODAGE_SORTIE, keep_default_na=False)
    libelles = registre.drop_duplicates("jeu").set_index("jeu")["libelle"].to_dict()

    fichiers = [
        (source / "registre_sources.csv", role, "registre-sources",
         "Registre des sources : fichier d'origine, pages retenues, empreinte SHA-256, URL, date de collecte."),
        (source / "bilan_sources.csv", role, "bilan-sources-retenues-ecartees",
         "Statut de chaque fichier remis par les organisateurs : retenu (avec les jeux concernés) "
         "ou écarté (avec le motif)."),
        (source / "inventaire_fichiers.csv", role, "inventaire-fichiers-organisateurs",
         "Inventaire de tous les fichiers remis par les organisateurs (format, taille, empreinte, dimensions)."),
        (source / "controle_couverture.csv", role, "controle-couverture-extractions",
         "Pages retenues par fichier pour les jeux sélectifs, avec alerte si aucune page n'est trouvée."),
    ]
    for chemin in sorted((source / "extraits").glob("*.csv")):
        fichiers.append((chemin, role, NOMS_DEPOT.get(chemin.stem, chemin.stem),
                         libelles.get(chemin.stem, chemin.stem)))

    entete = [
        "DÉPÔT 01 : COLLECTE - Défi 1, cartographie et anticipation du risque de décrochage scolaire",
        "",
        "Contenu : extractions brutes des données remises par les organisateurs (base principale DGESS",
        "2016-2025 et Data Pack DCB 2026). Les lignes sont copiées sans aucune modification ;",
        "la remise en forme est faite à l'étape 02 (nettoyage).",
        "",
        "Traçabilité : chaque ligne extraite porte le fichier d'origine (source_fichier), le CSV du pack",
        "(source_csv_pack), la période (source_periode) et, pour les PDF, la page et la ligne.",
        "Le registre des sources donne l'URL d'origine et l'empreinte SHA-256 de chaque fichier.",
        "Le bilan des sources indique, pour chaque fichier remis par les organisateurs, s'il a été",
        "retenu ou écarté, et pourquoi.",
        "",
        "Format : séparateur « ; », encodage UTF-8. Les nombres restent sous leur forme d'origine",
        "(virgule décimale, espace des milliers).",
        "",
        "Relancer : notebooks/01_collecte.ipynb, ou python -m sentinelle.collecte (avec src dans le PYTHONPATH).",
    ]
    return deposer(1, fichiers, entete, version)


# (fichier produit, rôle, description pour le nom, contenu pour le LISEZ-MOI)
TABLES_NETTOYAGE = [
    ("sentinelle_scolaire.gpkg", "architect", "base-sentinelle-scolaire-geopackage",
     "Base complète au format GeoPackage (s'ouvre dans QGIS) : 5 couches cartographiques, tables de référence, "
     "tables de faits, métadonnées et traçabilité."),
    ("meta_tables.csv", "architect", "metadonnees-description-des-tables",
     "Une ligne par table : contenu, grain, clé, sources, période, nombre de lignes et de colonnes."),
    ("meta_variables.csv", "architect", "metadonnees-dictionnaire-des-variables",
     "Dictionnaire : chaque variable de chaque table avec son type, son unité et sa description."),
    ("commune.csv", "engineer", "referentiel-communes-deux-decoupages",
     "351 communes avec P-codes et rattachements dans le découpage 2025 (17 régions, 47 provinces) "
     "et l'ancien (13 régions, 45 provinces)."),
    ("province.csv", "engineer", "referentiel-provinces-decoupage-2025",
     "47 provinces de 2025, avec l'ancienne province d'origine et l'indication des deux provinces scindées."),
    ("province_ancienne.csv", "engineer", "referentiel-provinces-ancien-decoupage",
     "45 anciennes provinces, avec les provinces de 2025 qui en sont issues."),
    ("region.csv", "engineer", "referentiel-regions-decoupage-2025", "17 régions de 2025."),
    ("region_ancienne.csv", "engineer", "referentiel-regions-ancien-decoupage", "13 anciennes régions."),
    ("ref_alias_nom.csv", "engineer", "alias-noms-provinces-regions",
     "Correspondance entre les orthographes rencontrées et les codes de l'ancien découpage."),
    ("fait_flux_publie.csv", "engineer", "taux-abandon-redoublement-publies-province-2017-2025-propre",
     "Taux de promotion, redoublement et abandon publiés par la DGESS, par province, classe et sexe, "
     "éditions 2017-2018 à 2024-2025, en format long."),
    ("fait_effectifs_retenus.csv", "engineer", "effectifs-redoublants-province-classe-sexe-propre",
     "Effectifs et redoublants par province, classe et sexe, une valeur par année (édition la plus récente), "
     "avec l'indicateur de fiabilité de la répartition par sexe."),
    ("fait_effectifs_editions.csv", "engineer", "effectifs-redoublants-toutes-editions",
     "Effectifs et redoublants tels que publiés dans chacune des huit éditions, pour vérifier les révisions."),
    ("fait_esu_province.csv", "engineer", "ecoles-fermees-rouvertes-province-esu-propre",
     "Écoles primaires fermées et rouvertes, élèves et enseignants concernés, par province et par rapport ; "
     "rapport_fiable indique les rapports dont la somme des provinces retrouve le total publié."),
    ("fait_esu_region.csv", "engineer", "etablissements-fermes-region-mensuel-2021-2023",
     "Établissements fermés, élèves et enseignants affectés, par région et par mois, de novembre 2021 à mai 2023."),
    ("fait_pdi_commune.csv", "engineer", "deplaces-internes-commune-mensuel-2019-2023-propre",
     "Personnes déplacées internes et enfants déplacés par commune (P-code 2025) et par date, 2019 à 2023."),
    ("meta_journal_nettoyage.csv", "engineer", "journal-de-nettoyage",
     "Chaque correction, déduction, rapprochement ou ligne écartée, avec la valeur avant et après et le motif."),
    ("meta_controles.csv", "engineer", "controles-automatiques-synthese",
     "Résultat des contrôles automatiques : complétude, cohérence, sommes contre totaux publiés, jointure "
     "avec les contours, métadonnées."),
    ("controle_sommes_regions.csv", "engineer", "controle-somme-provinces-totaux-regionaux",
     "Somme des provinces comparée aux totaux régionaux de l'annuaire et de la base principale."),
    ("controle_sommes_nationales.csv", "engineer", "controle-somme-provinces-total-national",
     "Somme des 45 provinces comparée au total national de la base principale."),
    ("controle_repartition_sexes.csv", "engineer", "controle-repartition-filles-garcons",
     "Entités et années où le rapport filles / garçons publié est invraisemblable."),
    ("controle_esu_totaux_primaire.csv", "engineer", "controle-esu-somme-provinces-total-publie",
     "Pour chaque rapport ESU, somme des provinces comparée au total primaire publié, et fiabilité retenue."),
]


def exporter_nettoyage(version: int = 1) -> pd.DataFrame:
    """Dépôt de l'étape 02 : base GeoPackage, tables propres, métadonnées, journal, contrôles, contours web."""
    source = config.SORTIE_NETTOYAGE
    fichiers = [(source / f, role, desc, contenu) for f, role, desc, contenu in TABLES_NETTOYAGE]
    for chemin in sorted(config.CONTOURS_WEB.glob("*.geojson")):
        fichiers.append((chemin, "engineer", f"contours-web-{chemin.stem.replace('_', '-')}",
                         f"Contours simplifiés pour le web ({chemin.stem}), sans trou entre entités, WGS 84."))
    entete = [
        "DÉPÔT 02 : NETTOYAGE - Défi 1, cartographie et anticipation du risque de décrochage scolaire",
        "",
        "Contenu : base Sentinelle Scolaire construite à partir des extractions de l'étape 01.",
        "Tables en format long, une valeur par ligne, avec le fichier et la page d'origine.",
        "Référentiel géographique : la commune (COD-AB, août 2025) relie l'ancien découpage (13 régions,",
        "45 provinces), utilisé par toutes les données DGESS, et le découpage de juillet 2025 (17 régions,",
        "47 provinces).",
        "",
        "Corrections : toutes consignées dans le journal de nettoyage (valeur avant, valeur après, motif).",
        "Contrôles : complétude (45 provinces sur 45), cohérence garçons + filles = total, somme des",
        "provinces contre les totaux régionaux et nationaux publiés, jointure complète avec les contours.",
        "Limites signalées : répartition filles / garçons invraisemblable dans l'annuaire 2024-2025 pour",
        "31 provinces (seul le total est utilisable) ; rapports ESU lus par OCR non fiables au niveau",
        "provincial ; à partir d'octobre 2023 les rapports ESU ne recensent plus les fermetures.",
        "",
        "Métadonnées : meta_tables (une ligne par table) et meta_variables (dictionnaire des variables).",
        "",
        "Format : séparateur « ; », encodage UTF-8, point décimal. Coordonnées en WGS 84 (EPSG:4326).",
        "",
        "Relancer : notebooks/02_nettoyage.ipynb, ou python -m sentinelle.nettoyage (avec src dans le PYTHONPATH).",
    ]
    return deposer(2, fichiers, entete, version)
