"""Préparation des dépôts selon la convention du challenge.

Modèle : EQUIPE_ETAPE_DEFI_ROLE_description_vN.extension
Exemple : SENTINELLE_02-nettoyage_D1_engineer_effectifs-primaire-propres_v1.csv
"""

from __future__ import annotations

import re
import shutil
import unicodedata
import zipfile
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
# Dossiers de dépôt : noms donnés par le document du challenge (section 4, colonne « Dépôt »).
DOSSIERS = {
    1: "01_collecte",
    2: "02_nettoyage",
    3: "03_transformation",
    4: "04_analyse",
    5: "05_interpretation",
}
ROLES = {"engineer", "architect", "analyst", "scientist"}
DOCUMENTS = config.RACINE / "docs"


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
    """Copie des fichiers dans depots/<dossier de l'étape> sous leur nom normalisé et écrit le LISEZ-MOI.

    ``fichiers`` : liste de (chemin produit, rôle, description pour le nom, contenu pour le LISEZ-MOI).
    Le dossier de l'étape est vidé au préalable pour qu'aucun fichier périmé ne subsiste.
    """
    cible = config.verifier_ecriture(config.DEPOTS / DOSSIERS[etape])
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

    # Le LISEZ-MOI porte le rôle qui a déposé le plus de fichiers dans l'étape.
    role_lisez_moi = table["role"].value_counts().idxmax() if not table.empty else "engineer"
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
    ("fait_base_principale.csv", "engineer", "base-principale-dgess-prescolaire-primaire-2016-2025-propre",
     "Les 21 tableaux de la base principale DGESS en format long : effectifs du préscolaire et du primaire "
     "(région, statut, milieu, niveau, sexe), nouveaux inscrits au CP1, TBA, TBS, taux d'achèvement, réussite "
     "au CEP, indices de parité, écoles, structures et salles du préscolaire, 2015-2016 à 2024-2025."),
    ("fait_enf_province.csv", "engineer", "education-non-formelle-centres-apprenants-province-2018-2024-propre",
     "Éducation non formelle par province et milieu, campagnes 2018, 2019, 2020 et 2024 : centres des adultes et "
     "des adolescents, apprenants adultes (1er et 2nd cycle) et adolescents, dont femmes ; doublon du Data Pack écarté."),
    ("fait_prescolaire_province.csv", "engineer", "prescolaire-taux-sections-province-2023-2025-propre",
     "Préscolaire par province et sexe, 2023-2024 et 2024-2025 : population préscolarisable, enfants préscolarisés, "
     "taux de préscolarisation, enfants par section."),
    ("fait_conditions_vie.csv", "engineer", "pauvrete-conditions-vie-commune-province-rgph-2019-propre",
     "Pauvreté, emploi, travail des enfants, enfants hors de l'école, alphabétisation, mariage précoce, actes de "
     "naissance, eau, électricité, téléphone : 351 communes, 45 provinces, 13 régions, pays (INSD, RGPH 2019, vol. 3)."),
    ("fait_conditions_scolarisation.csv", "engineer", "conditions-scolarisation-province-2017-2025-propre",
     "Seize tableaux par province des annuaires DGESS, 8 éditions : équipement des écoles (eau, électricité, latrines, "
     "cantines), distance parcourue, taille des écoles, logements de maîtres, manuels, mobilier, profession des parents, "
     "surface, ancienneté et état des salles, TBA, TBS, TNS, achèvement, CEP."),
    ("fait_profils_pauvrete.csv", "engineer", "consommation-inegalites-province-commune-profils-pauvrete-propre",
     "Consommation par personne, sévérité de la pauvreté, Gini et autres inégalités par province et commune (10 régions), "
     "d'après les profils régionaux de l'INSD (2023), année de référence 2019."),
    ("fait_repartitions_province.csv", "engineer", "eleves-entrants-par-age-enseignants-province-2017-2025-propre",
     "Élèves et nouveaux entrants au CP1 par âge et sexe, enseignants par sexe, âge et expérience, par province, "
     "8 éditions de l'annuaire du primaire."),
    ("fait_causes_abandon.csv", "engineer", "abandons-orpaillage-mariage-grossesse-region-2017-2023-propre",
     "Abandons déclarés pour orpaillage, mariage et grossesse par région, primaire 2016-2017 à 2022-2023 et "
     "post-primaire 2021-2022 et 2022-2023 (tableaux de bord DGESS)."),
    ("fait_secondaire_province.csv", "engineer", "tba-tbs-achevement-flux-secondaire-province-2018-2023-propre",
     "Post-primaire et secondaire par province : TBA en 6e et 2nde, TBS, taux nets, achèvement et flux par classe, "
     "2018-2019 à 2022-2023 (annuaires DGESS)."),
    ("fait_tableau_bord_secondaire.csv", "engineer", "indicateurs-post-primaire-secondaire-region-pays-2020-2025",
     "Indicateurs des tableaux de bord DGESS, régions et pays ; séries nationales complémentaires sans extrapolation territoriale."),
    ("fait_secondaire_region.csv", "engineer", "commodites-salles-ratios-secondaire-region-2018-2023-propre",
     "Commodités, état des salles et ratio élèves par classe du secondaire général public, par région."),
    ("fait_insd_commune.csv", "engineer", "ecoles-eleves-enseignants-commune-insd-2014-2024-propre",
     "Effectifs scolaires par commune (13 régions) : écoles, salles, élèves et enseignants du primaire, élèves du "
     "post-primaire et du secondaire, d'après les annuaires régionaux 2024 de l'INSD."),
    ("fait_population.csv", "engineer", "population-age-simple-sexe-communes-provinces-2007-2035-propre",
     "Population par âge simple et sexe des 351 communes (2020-2025), des 47 provinces et 17 régions de 2025 "
     "(2020-2035) et du pays (2007-2018, 2020-2035), projections actualisées de l'INSD."),
    ("fait_mines_region.csv", "engineer", "permis-sites-miniers-region-propre",
     "Permis d'exploitation et sites miniers par typologie et par région (annuaires régionaux INSD), série lacunaire "
     "conservée pour mémoire."),
    ("fait_offre_province.csv", "engineer", "ecoles-salles-maitres-eleves-province-2017-2025-propre",
     "Écoles, salles, groupes pédagogiques, maîtres et élèves par province et statut, avec les élèves par maître "
     "et par salle."),
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
    fichiers.append((DOCUMENTS / "methodologie" / "methodologie_donnees.pdf", "architect",
                     "documentation-technique-collecte-nettoyage",
                     "Document technique : sources retenues et écartées, méthode de collecte et de nettoyage, "
                     "référentiel à deux découpages, contrôles, limites, reproduction."))
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


def exporter_transformation(version: int = 1) -> pd.DataFrame:
    """Dépôt de l'étape 03 : table d'analyse, panel mensuel, dictionnaire des variables, schéma des relations."""
    source = config.DONNEES / "03_transformation"
    fichiers = [
        (source / "panel_province_annee.csv", "engineer", "table-analyse-risque-decrochage-province-annee",
         "Une ligne par province (45) et année scolaire t : cible (abandon entre t et t+1, ou rupture de "
         "scolarisation) et variables connues en t (passé scolaire, effectifs, offre, déplacés, écoles fermées)."),
        (source / "panel_mensuel_province.csv", "engineer", "deplaces-ecoles-fermees-province-mensuel",
         "Déplacés internes par province et par relevé mensuel, avec leurs évolutions, et écoles fermées de la "
         "région : base de l'alerte entre deux annuaires."),
        (source / "panel_region_annee.csv", "engineer", "indicateurs-regionaux-base-principale-2016-2025",
         "Une ligne par région (13, ancien découpage) et pour le pays, par année de 2015-2016 à 2024-2025 : "
         "effectifs, nouveaux inscrits au CP1, TBA, TBS, taux d'achèvement, réussite au CEP, indices de parité, "
         "écoles, préscolaire (effectifs, TBS, structures, salles)."),
        (source / "sentinelle_base_finale_decoupage_2025.xlsx", "engineer", "base-finale-decoupage-2025-par-ordre",
         "Base finale du découpage de 2025 en classeur : un onglet par panel (province, région) et par ordre "
         "d'enseignement (primaire, préscolaire, non formel, post-primaire, post-primaire et secondaire, tous ordres, "
         "contexte), et un onglet décrivant chaque variable."),
        (source / "panel_commune_annee.csv", "engineer", "panel-communal-vulnerabilite-2016-2025",
         "Panel des 351 communes, 2016-2017 à 2024-2025 : élèves, enseignants et salles des annuaires de l'INSD, "
         "population par âge, taux de scolarisation communaux, déplacés, conditions de vie de 2019."),
        (source / "panel_province_2025.csv", "engineer", "table-analyse-province-decoupage-2025",
         "Panel du modèle dans le découpage de juillet 2025 (47 provinces, noms et codes du COD-AB) ; Soum et Tapoa "
         "scindés : effectifs répartis par clés communales de l'INSD, déplacés et RGPH recalculés sur les communes, "
         "cible non observée (valeur de la province d'origine gardée à part)."),
        (source / "base_apuree" / "base_apuree.csv", "engineer", "base-apuree-province-2025-sans-cellule-vide",
         "Base apurée : panel provincial de 2025 réduit à 79 colonnes, sans cellule vide ; valeurs impossibles "
         "recodées, manquants imputés (méthode choisie par test), valeurs publiées de l'INSD pour le post-primaire."),
        (source / "base_apuree" / "statut_cellules.csv", "engineer", "statut-cellules-base-apuree",
         "Statut de chaque cellule de la base apurée (observée, valeur publiée INSD, imputée, complétée) et méthode : "
         "seules les cibles observées servent à entraîner et évaluer un modèle."),
        (source / "base_apuree" / "journal_apurement.csv", "engineer", "journal-apurement",
         "Une ligne par cellule recodée, sourcée ou imputée : étape, valeur avant et après, méthode, justification."),
        (source / "base_apuree" / "base_defi1_apuree.xlsx", "engineer", "classeur-base-apuree",
         "Classeur de la base apurée : cellules colorées selon leur statut, rapport par variable, synthèse des "
         "méthodes, journal, sources INSD retenues et rejetées, variables retirées, contrôles."),
        (source / "base_apuree" / "controles_apurement.csv", "engineer", "controles-apurement",
         "Contrôles de l'apurement : aucune cellule vide, valeurs observées inchangées, flux = 100, proportions "
         "dans [0 ; 1], sources INSD contrôlées."),
        (source / "base_apuree" / "base_apuree_par_sexe.csv", "engineer", "base-apuree-par-sexe",
         "Base apurée par sexe : 47 provinces × 9 années × filles et garçons ; 26 variables publiées par sexe "
         "(flux, effectifs, taux, âges, post-primaire, secondaire) ancrées sur l'ensemble de la base apurée, et "
         "variables communes aux deux sexes."),
        (source / "base_apuree" / "statut_cellules_par_sexe.csv", "engineer", "statut-cellules-par-sexe",
         "Statut de chaque cellule par sexe (observée ou imputée) et méthode."),
        (source / "base_apuree" / "controles_apurement_par_sexe.csv", "engineer", "controles-apurement-par-sexe",
         "Contrôles de la base par sexe : aucune cellule vide, valeurs observées égales aux annuaires, filles et "
         "garçons redonnent l'ensemble."),
        (source / "panel_region_2025.csv", "engineer", "indicateurs-regionaux-decoupage-2025",
         "Indicateurs régionaux dans les 17 régions de 2025 et pour le pays ; régions scindées : effectifs répartis "
         "selon les élèves des provinces, taux hérités."),
        (source / "serie_nationale_annee.csv", "engineer", "serie-nationale-statut-milieu-classe-2016-2025",
         "Une ligne par année : indicateurs nationaux et ventilations publiées seulement au niveau national "
         "(public et privé, urbain et rural, effectifs par classe, préscolaire par statut, milieu et section)."),
        (source / "dictionnaire_variables_modele.csv", "architect", "dictionnaire-variables-table-analyse",
         "Chaque variable de la table d'analyse : rôle (identifiant, cible, explicative), description, source, "
         "part de valeurs manquantes, années couvertes."),
        (source / "dictionnaire_variables_region.csv", "architect", "dictionnaire-variables-region-nation",
         "Description, source et part de valeurs manquantes des variables des tables régionale et nationale."),
        (source / "schema_relations.csv", "architect", "schema-relations-entre-tables",
         "Clés de jointure entre la table d'analyse, les tables de la base et les couches cartographiques."),
        (source / "metadonnees" / "dictionnaire_bases_modele.csv", "architect", "metadonnees-variables-bases-modele",
         "Une fiche par variable des bases du modèle : libellé, description, rôle, unité, type, plage ou modalités, "
         "part manquante, années, mode de calcul, source, limites."),
        (source / "metadonnees" / "tables_bases_modele.csv", "architect", "metadonnees-tables-bases-modele",
         "Une ligne par base du modèle : contenu, grain, clé, liens, usage, taille, période."),
        (source / "metadonnees" / "datapackage.json", "architect", "metadonnees-datapackage-frictionless",
         "Description des bases du modèle au format standard Frictionless Data Package : schémas, clés, liens."),
        (source / "metadonnees" / "dictionnaire_bases_modele.html", "architect", "dictionnaire-lisible-bases-modele",
         "Dictionnaire lisible des bases du modèle (s'ouvre dans un navigateur, imprimable en PDF)."),
        (DOCUMENTS / "methodologie" / "passage_decoupage_2025.pdf", "architect",
         "documentation-technique-passage-decoupage-2025",
         "Document technique : table de passage vers les 17 régions et 47 provinces de 2025, méthode de calcul de "
         "chaque variable pour les provinces scindées, contrôles, limites."),
        (DOCUMENTS / "documentation" / "figures" / "fig_parcours.png", "architect", "plan-parcours-des-donnees",
         "Plan du parcours des données, des sources à la décision : cinq étapes, modules, dépôts et rôles."),
        (source / "controles_transformation.csv", "engineer", "controles-transformation",
         "Contrôles : unicité des lignes, cible renseignée, aucune variable venant du futur, variables décrites, "
         "jointure avec la carte de 2025, cohérence des tables régionale et nationale."),
    ]
    entete = [
        "DÉPÔT 03 : TRANSFORMATION - Défi 1, cartographie et anticipation du risque de décrochage scolaire",
        "",
        "Contenu : tables d'analyse construites à partir de la base nettoyée (dépôt 02).",
        "La table principale compte une ligne par province (45, ancien découpage) et par année scolaire t,",
        "de 2016-2017 à 2024-2025. La cible est l'abandon apparent du cycle CP1-CM1 entre t et t+1 ; quand",
        "les effectifs varient de plus de 30 % entre t et t+1, la ligne est classée en rupture de",
        "scolarisation (fermetures ou réouvertures massives) et la cible est laissée vide. Les variables",
        "explicatives ne portent que sur l'année t ou les précédentes.",
        "",
        "La base principale DGESS est exploitée en entier : le contexte de la région entre dans la table",
        "principale (TBA, TBS, taux d'achèvement, parité, préscolaire, réussite au CEP de la session",
        "précédente), une table régionale reprend tous les indicateurs régionaux et une série nationale",
        "les ventilations par statut, milieu et classe.",
        "",
        "Les valeurs absentes des sources restent vides. Pour la carte, chaque province de 2025 reçoit",
        "la valeur de la province dont elle est issue (colonne provinces_actuelles).",
        "",
        "La base apurée (dossier base_apuree) part du panel de 2025 : 79 colonnes, aucune cellule vide, et le",
        "statut de chaque cellule (observée, valeur publiée INSD, imputée, complétée). La base par sexe",
        "(base_apuree_par_sexe) donne les mêmes provinces et années pour les filles et les garçons.",
        "",
        "Relancer : python -m sentinelle.transformation puis python -m sentinelle.apurement (avec src dans le",
        "PYTHONPATH), ou notebooks/03_transformation.ipynb puis notebooks/03b_apurement.ipynb.",
    ]
    return deposer(3, fichiers, entete, version)


# Étape 04 ----------------------------------------------------------------------------------------

EXPLORATION = {
    "variance_cible": ("variance-cible-annees-provinces", "Part de la variance du taux d'abandon due aux années, aux provinces et aux ruptures."),
    "cible_par_annee": ("taux-abandon-par-annee", "Taux d'abandon observé par année : moyenne, médiane, dispersion, nombre de ruptures."),
    "ruptures": ("ruptures-de-scolarisation", "Lignes en rupture (variation des effectifs de plus de 30 %), exclues du modèle d'abandon."),
    "correlations": ("liens-variables-cible", "Lien de chaque variable avec la cible (corrélation de rang), année par année et en moyenne."),
    "groupes_colineaires": ("groupes-variables-colineaires", "Groupes de variables trop liées entre elles (|rho| >= 0,85) et représentant gardé."),
    "decision_variables": ("decision-garder-retirer-variables", "Décision motivée de garder ou de retirer chaque variable."),
    "variables_modele": ("listes-variables-modeles", "Variables gardées pour les modèles linéaires et pour les modèles d'arbres."),
}
MODELISATION = {
    "tableau_de_bord": ("scientist", "previsions-tableau-de-bord-province-2025-2028",
                        "Prévision 2025-2026 et projections 2026-2027 et 2027-2028 par province, intervalle à 80 %, "
                        "classe de risque, facteurs principaux, score et classe de rupture."),
    "previsions": ("scientist", "previsions-par-horizon-province", "Prévisions à 1, 2 et 3 ans du modèle retenu, avec bornes."),
    "synthese_modeles": ("scientist", "fiabilite-erreurs-dix-modeles", "Erreur absolue moyenne, corrélation de rang et rappel du "
                         "quintile le plus à risque de dix modèles, plis de sélection et test final, à 1, 2 et 3 ans."),
    "evaluation_plis": ("scientist", "fiabilite-erreurs-par-pli", "Mêmes mesures pour chaque pli de validation dans le temps."),
    "intervalle": ("scientist", "fiabilite-couverture-intervalles", "Marge conforme et couverture observée de l'intervalle à 80 % au test final."),
    "seuils_classes": ("scientist", "seuils-classes-risque", "Seuils des classes de risque (médiane et 80e centile des taux prévus)."),
    "reglages": ("scientist", "reglages-retenus", "Réglages choisis sur les plis de sélection et modèle retenu."),
    "grille_reglages": ("scientist", "grille-reglages-testes", "Erreur de chaque réglage testé sur les plis de sélection."),
    "variables_retenues": ("scientist", "variables-retenues-par-pli", "Fréquence de chaque variable retenue dans les plis."),
    "courbe_elimination_prevision": ("scientist", "elimination-shap-prevision", "Courbe d'élimination récursive guidée par SHAP (prévision)."),
    "explication_validation": ("scientist", "fiabilite-explication-provinces-non-vues", "Part de variance expliquée sur des provinces non vues."),
    "explication_courbe_elimination": ("scientist", "elimination-shap-explication", "Courbe d'élimination récursive guidée par SHAP (explication)."),
    "explication_variables_retenues": ("scientist", "variables-explication", "Variables des deux volets de l'explication."),
    "explication_facteurs": ("scientist", "facteurs-par-province", "Trois facteurs qui élèvent le niveau de chaque province et son principal frein."),
    "explication_contributions": ("scientist", "valeurs-shap-par-province", "Contribution SHAP de chaque variable au niveau de chaque province (points)."),
    "explication_valeurs": ("scientist", "valeurs-variables-explication", "Valeurs des variables de l'explication pour chaque province."),
    "explication_valeur_de_base": ("scientist", "valeur-de-base-shap", "Valeur de départ des contributions SHAP (moyenne des provinces)."),
    "explication_importance": ("scientist", "importance-facteurs-nationale", "Importance moyenne et sens de chaque facteur."),
    "explication_effets_lineaires": ("scientist", "effets-chiffres-elastic-net", "Effet de chaque variable en points de taux (elastic net)."),
    "alerte_rupture": ("scientist", "alerte-rupture-2025-2026", "Score et classe de rupture de scolarisation par province pour 2025-2026."),
    "evaluation_alerte_rupture": ("scientist", "fiabilite-alerte-rupture", "AUC de l'alerte de rupture et ruptures retrouvées, par année."),
    "coefficients_alerte_rupture": ("scientist", "coefficients-alerte-rupture", "Coefficients standardisés du modèle d'alerte."),
    "contributions_alerte_rupture": ("scientist", "contributions-alerte-rupture-province", "Contribution de chaque signal au score de chaque province."),
}


def _zipper(dossiers: list[Path], archive: Path) -> Path:
    """Archive ZIP des fichiers de code, sans les caches."""
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for dossier in dossiers:
            for f in sorted(dossier.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    z.write(f, f.relative_to(config.RACINE).as_posix())
    return archive


def exporter_analyse(version: int = 1) -> pd.DataFrame:
    """Dépôt de l'étape 04 : exploration (analyst), modèle, fiabilité, prévisions, explication, alerte (scientist)."""
    source = config.DONNEES / "04_analyse"
    fichiers = []
    for jeu, libelle in [("ensemble", "ensemble"), ("sexe", "par-sexe")]:
        for nom, (desc, contenu) in EXPLORATION.items():
            fichiers.append((source / "exploration" / f"{nom}_{jeu}.csv", "analyst", f"{desc}-{libelle}",
                             f"{contenu} ({'ensemble des élèves' if jeu == 'ensemble' else 'filles et garçons'})."))
        for nom, (role, desc, contenu) in MODELISATION.items():
            suffixe = "" if nom.endswith("alerte_rupture") else f"_{jeu}"
            if suffixe == "" and jeu == "sexe":
                continue
            fichiers.append((source / "modelisation" / f"{nom}{suffixe}.csv", role,
                             desc if not suffixe else f"{desc}-{libelle}", contenu))
        modeles = source / "modeles" / jeu
        fichiers += [
            (modeles / "fiche_modele.json", "scientist", f"fiche-modele-{libelle}",
             "Fiche du modèle : cible, normalisation, modèle retenu, règle de choix, marges, seuils, réglages, "
             "variables, qualité mesurée, versions des bibliothèques."),
            (modeles / "explication_lightgbm.txt", "scientist", f"modele-lightgbm-facteurs-{libelle}",
             "Modèle LightGBM des facteurs par province, format texte relisible sans Python."),
            (modeles / "explication_lightgbm.joblib", "scientist", f"modele-lightgbm-facteurs-{libelle}-python",
             "Même modèle sauvegardé pour Python (joblib), avec ses variables."),
            (modeles / "explication_elastic_net.joblib", "scientist", f"modele-elastic-net-effets-{libelle}",
             "Elastic net des effets chiffrés (simulateur), avec ses paramètres de normalisation."),
        ]
    fichiers.append((source / "modeles" / "ensemble" / "alerte_rupture.joblib", "scientist", "modele-alerte-rupture",
                     "Régression logistique de l'alerte de rupture, avec ses variables, sa normalisation et ses seuils."))
    code = _zipper([config.RACINE / "src" / "sentinelle" / "analyse"], source / "code_modele_sentinelle_analyse.zip")
    fichiers.append((code, "scientist", "code-modele-prevision-explication-alerte",
                     "Code du modèle (paquet sentinelle.analyse) : préparation, dix modèles de prévision, choix, "
                     "intervalle conforme, explication SHAP, alerte de rupture, sauvegarde."))
    notebooks = config.RACINE / "notebooks"
    fichiers += [
        (notebooks / "04a_exploration.ipynb", "analyst", "notebook-analyse-exploratoire",
         "Notebook exécuté de l'analyse exploratoire : cible, variance, ruptures, liens, décisions sur les variables."),
        (notebooks / "04b_modelisation.ipynb", "scientist", "notebook-modelisation-fiabilite",
         "Notebook exécuté de la modélisation : comparaison des modèles, fiabilité, intervalles, alerte."),
        (notebooks / "04c_explicabilite.ipynb", "scientist", "notebook-explicabilite-shap",
         "Notebook exécuté de l'explicabilité : effets chiffrés, valeurs SHAP, facteurs par province."),
    ]
    entete = [
        "DÉPÔT 04 : ANALYSE - Défi 1, cartographie et anticipation du risque de décrochage scolaire",
        "",
        "Contenu : analyse exploratoire (rôle analyst) puis modèle du décrochage (rôle scientist), pour",
        "l'ensemble des élèves et pour les filles et les garçons.",
        "",
        "Cible : taux d'abandon du primaire de chaque province (47 provinces de 2025), normalisé en logit.",
        "Les années de rupture (effectifs en variation de plus de 30 %) sont traitées par une alerte à part.",
        "",
        "Prévision : dix modèles comparés dans le temps (trois plis de sélection, puis 2024-2025 en test",
        "final jamais utilisé pour choisir). Modèle retenu : retour amorti vers le niveau habituel de la",
        "province. Erreur au test final : 3,3 points (ensemble). Intervalle conforme à 80 %, couverture",
        "de 85 à 88 % au test. Horizons : 2025-2026, 2026-2027 et 2027-2028.",
        "Explication : LightGBM après élimination récursive guidée par SHAP et elastic net, validés sur des",
        "provinces non vues. Les facteurs sont des associations, pas des causes.",
        "Alerte de rupture : régression logistique sur sept signaux, AUC de 0,85 à 0,96.",
        "",
        "Format : séparateur « ; », encodage UTF-8. Modèles en joblib (Python) et en texte (LightGBM).",
        "",
        "Relancer : python -m sentinelle.analyse.exploration puis python -m sentinelle.analyse.modelisation",
        "(avec src dans le PYTHONPATH), ou les notebooks 04a, 04b et 04c.",
    ]
    return deposer(4, fichiers, entete, version)


# Étape 05 ----------------------------------------------------------------------------------------

def exporter_interpretation(version: int = 1) -> pd.DataFrame:
    """Dépôt de l'étape 05 : indicateurs clés, carte d'alerte, rapports, guide et code du tableau de bord."""
    source = config.DONNEES / "05_interpretation"
    fichiers = [
        (source / "indicateurs_cles_province.csv", "analyst", "indicateurs-cles-province-2024-2028",
         "Par province : taux observé 2024-2025, taux prévus 2025-2026 à 2027-2028 avec intervalle et classe, "
         "nombre estimé d'élèves qui abandonnent, alerte de rupture, facteurs principaux."),
        (source / "indicateurs_cles_region.csv", "analyst", "indicateurs-cles-region-pays-2024-2028",
         "Par région et pour le pays : taux pondéré par les effectifs, nombre estimé d'abandons, provinces en "
         "risque élevé, alertes de rupture."),
        (source / "carte_alerte_2025_2026.png", "analyst", "carte-alerte-risque-decrochage-2025-2026",
         "Carte des classes de risque de décrochage en 2025-2026, alertes de rupture en hachures."),
        (source / "rapports" / "rapport_national.pdf", "analyst", "rapport-national-decision",
         "Rapport national : chiffres clés, carte, classement, provinces qui résistent, facteurs, pistes d'action."),
        (source / "rapports" / "rapports_regions.zip", "analyst", "rapports-17-regions",
         "Rapport de chacune des 17 régions : carte, provinces, priorités et pistes d'action (PDF)."),
        (source / "rapports" / "rapports_provinces.zip", "analyst", "fiches-47-provinces",
         "Fiche de décision de chacune des 47 provinces : prévision, intervalle, évolution, facteurs, filles et "
         "garçons, rupture, pistes d'action (PDF)."),
        (DOCUMENTS / "documentation" / "documentation_sentinelle.pdf", "analyst", "documentation-solution",
         "Documentation de la solution (15 pages au plus, plan du challenge) : défi, données, préparation, méthode "
         "et évaluation des modèles, résultats et interprétation des prévisions, réponse au défi, reproduction."),
        (source / "guide_sentinelle.pdf", "analyst", "guide-utilisation-tableau-de-bord",
         "Guide d'utilisation du tableau de bord Sentinelle Scolaire."),
        (source / "application_sentinelle_source.zip", "analyst", "tableau-de-bord-sentinelle-code",
         "Code du tableau de bord : API FastAPI, site Next.js (carte MapLibre, graphiques ECharts), image Docker, "
         "lancement local (lancer.bat) et déploiement."),
    ]
    entete = [
        "DÉPÔT 05 : INTERPRÉTATION ET VISUALISATION - Défi 1, risque de décrochage scolaire",
        "",
        "Solution : tableau de bord Sentinelle Scolaire, en ligne à l'adresse",
        "https://sentinelle-scolaire-bf.up.railway.app",
        "Vue nationale sur quatre années (2024-2025 observée, prévisions jusqu'en 2027-2028), fiche de",
        "chaque province, vue des régions, simulateur de leviers, mise à jour annuelle des données",
        "(import CSV ou saisie, sans réentraîner), assistant de questions-réponses, rapports PDF.",
        "",
        "Ce dépôt réunit ce qu'un décideur utilise sans ouvrir l'application : indicateurs clés, carte",
        "d'alerte, rapport national, rapports régionaux, fiches provinciales et guide d'utilisation.",
        "Le nombre estimé d'élèves qui abandonnent multiplie le taux par l'effectif du primaire de",
        "2024-2025 (effectifs futurs inconnus).",
        "",
        "Relancer : python -m sentinelle.interpretation (avec src dans le PYTHONPATH) produit ces fichiers.",
        "Le tableau de bord se lance avec application/lancer.bat (Windows, sans Internet) ou",
        "docker compose up --build ; voir application/README.md.",
    ]
    return deposer(5, fichiers, entete, version)
