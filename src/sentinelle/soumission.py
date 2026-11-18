"""Dossier unique à déposer sur la plateforme, rangé par catégorie (Code, Donnees, Documentation).

Chaque fichier suit le modèle du document du challenge, EQUIPE_ÉTAPE_DÉFI_RÔLE_description_vN, et appartient à une
seule étape : le code est découpé en une archive par étape. La plateforme accepte 20 fichiers de 50 Mo au plus.

Les fichiers viennent des dépôts de chaque étape (``depots/``) et des documents compilés. La version déposée de la
base finale diffère de la base de travail sur deux points, appliqués ici et décrits dans le LISEZ-MOI :

* les variables du recensement de 2019 (une seule mesure, répétée chaque année) portent le suffixe ``_2019`` ;
* les colonnes de suivi interne, déjà couvertes par ``statut_cellules`` et le journal, sont retirées.

Le code garde les noms courts en interne ; la correspondance est la table ``RENOMMEES_2019``.

Lancement, depuis ``defi1_sentinelle`` : ``python -m sentinelle.soumission``
Sortie : ``soumission/<catégorie>/`` (ignoré par Git), à téléverser tel quel.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from . import config
from .depots import DOSSIERS, ETAPES

SORTIE = config.RACINE / "soumission"
LIEN_APPLICATION = "https://sentinelle-scolaire-bf.up.railway.app"
LIMITE_OCTETS = 50 * 1024 * 1024
CATEGORIES = {"Code": "Code", "Données": "Donnees", "Documentation": "Documentation"}

# Variables publiées une seule fois (INSD, RGPH 2019, volume 3) et répétées chaque année scolaire.
RENOMMEES_2019 = {v: f"{v}_2019" for v in [
    "pauvrete_province", "travail_enfants_7_14_province", "emploi_15_24_province", "chomage_25_64_province",
    "frequentation_post_primaire_province", "frequentation_secondaire_province",
    "parite_scolarisation_primaire_province", "parite_scolarisation_post_primaire_province",
    "parite_scolarisation_secondaire_province", "hors_ecole_6_11_province", "hors_ecole_12_15_province",
    "hors_ecole_16_18_province", "ni_ecole_ni_emploi_15_24_province", "alphabetisation_adultes_province",
    "dependance_demographique_province", "filles_17_ans_mariees_province",
]}
# Colonnes de suivi interne de la chaîne : leur information est dans statut_cellules et journal_apurement.
RETIREES = [
    "methode_passage", "cible_observee", "methode_population", "nb_valeurs_imputees", "statut_imputation",
    "abandon_primaire_precedent_province_origine", "redoublement_primaire_precedent_province_origine",
]
MOTIF = re.compile(r"\b(" + "|".join(map(re.escape, RENOMMEES_2019)) + r")\b")

BASE = config.DONNEES / "03_transformation" / "base_apuree"
ROLE_ARCHIVE = {1: "engineer", 2: "engineer", 3: "engineer", 4: "scientist", 5: "analyst"}
# Code de chaque étape. Les chemins partent de la racine du projet : les cinq archives, décompressées au même
# endroit, redonnent le projet complet. Les modules communs et les fichiers d'installation sont dans chacune.
COMMUN = ["src/sentinelle/__init__.py", "src/sentinelle/config.py", "src/sentinelle/lecture.py",
          "src/sentinelle/indicateurs.py", "src/sentinelle/cartes.py", "src/sentinelle/depots.py",
          "README.md", "requirements.txt", "pyproject.toml", ".gitignore", ".gitattributes"]
CODE_ETAPE = {
    1: ("code-collecte-extraction-sources", "Code de la collecte : catalogue des sources, extraction, registre "
        "et notebook de l'étape.", ["src/sentinelle/collecte", "notebooks/01_collecte.ipynb"]),
    2: ("code-nettoyage-base-geopackage", "Code du nettoyage : harmonisation des noms, contrôles des totaux, base "
        "GeoPackage et notebook de l'étape.", ["src/sentinelle/nettoyage", "notebooks/02_nettoyage.ipynb"]),
    3: ("code-transformation-apurement", "Code de la transformation (panels, passage au découpage de 2025) et de "
        "l'apurement (base finale sans cellule vide), avec les notebooks.",
        ["src/sentinelle/transformation", "src/sentinelle/apurement", "notebooks/03_transformation.ipynb",
         "notebooks/03b_apurement.ipynb"]),
    4: ("code-prevision-explication-alerte", "Code de l'analyse : exploration, prévisions avec intervalles, "
        "explication SHAP, alerte de rupture, fiabilité, avec les notebooks exécutés.",
        ["src/sentinelle/analyse", "notebooks/04a_exploration.ipynb", "notebooks/04b_modelisation.ipynb",
         "notebooks/04c_explicabilite.ipynb"]),
    5: ("code-tableau-de-bord-rapports", "Code de l'interprétation et du tableau de bord (API FastAPI, site "
        "Next.js, Dockerfile), tests, sources de la documentation et sorties légères que l'application relit.",
        ["src/sentinelle/interpretation", "src/sentinelle/soumission.py", "application", "tests", ".dockerignore",
         "docs/documentation", "data/LISEZ-MOI.md", "data/02_nettoyage/contours_web",
         "data/03_transformation/base_apuree", "data/03_transformation/dictionnaire_variables_modele.csv",
         "data/03_transformation/metadonnees/dictionnaire_bases_modele.csv", "data/04_analyse"]),
}
EXCLUS_CODE = {"node_modules", ".next", "deploiement", "__pycache__", ".pytest_cache", ".ruff_cache",
               ".ipynb_checkpoints"}
FICHIERS_EXCLUS_CODE = {".env", "next-env.d.ts", "tsconfig.tsbuildinfo"}
SUFFIXES_EXCLUS_CODE = {".pyc", ".log", ".blg", ".aux", ".out"}
DOCUMENTS = [
    (2, "architect", config.RACINE / "docs/methodologie/methodologie_donnees.pdf",
     "document-technique-collecte-nettoyage-donnees",
     "Document technique : collecte, nettoyage et contrôle des données."),
    (3, "architect", config.RACINE / "docs/methodologie/passage_decoupage_2025.pdf",
     "document-technique-passage-decoupage-2025",
     "Document technique : passage des données au découpage administratif de 2025."),
    (5, "analyst", config.RACINE / "docs/documentation/documentation_sentinelle.pdf", "rapport-sentinelle",
     "**Rapport Sentinelle** : documentation de la solution (format IJCAI, 14 pages) : données, méthode, performances, prévisions, "
     "application, limites."),
    (5, "analyst", config.RACINE / "application/web/public/guide_sentinelle.pdf",
     "guide-utilisation-tableau-de-bord", "Guide d'utilisation du tableau de bord, écran par écran."),
]


SEXE = {"libelle": "Sexe des élèves", "description": "Filles ou garçons (base par sexe seulement)",
        "role": "identifiant", "type": "texte", "source": "DGESS, base principale"}


# Variables de la seule base par sexe (annuaires du secondaire, DGESS), absentes du dictionnaire des panels.
SOURCE_SECONDAIRE = "DGESS, annuaires statistiques du post-primaire et du secondaire, 2018-2019 à 2022-2023"
PAR_SEXE = {
    "tba_2nde_province": ("Taux brut d'admission en 2nde", "%"),
    "tbs_secondaire_province": ("Taux brut de scolarisation au secondaire", "%"),
    "achevement_secondaire_province": ("Taux d'achèvement du secondaire", "%"),
    "abandon_secondaire_province": ("Taux d'abandon au secondaire (moyenne des flux de 2nde et 1re)", "%"),
    "redoublement_terminale_province": ("Taux de redoublement en terminale", "%"),
}


def renommer_texte(texte: str) -> str:
    return MOTIF.sub(lambda m: RENOMMEES_2019[m.group(1)], texte)


def base_deposee(table: pd.DataFrame) -> pd.DataFrame:
    """Base finale telle que déposée : colonnes de suivi retirées, variables de 2019 suffixées."""
    return table.drop(columns=[c for c in RETIREES if c in table.columns]).rename(columns=RENOMMEES_2019)


def _lire(chemin: Path) -> pd.DataFrame:
    return pd.read_csv(chemin, sep=";", encoding="utf-8-sig", low_memory=False)


def _ecrire_csv(table: pd.DataFrame) -> bytes:
    return table.to_csv(sep=";", index=False).encode("utf-8-sig")


def _table_deposee(chemin: Path) -> bytes:
    """CSV d'une étape : base retaillée si elle contient les colonnes de suivi, noms de 2019 partout."""
    texte = chemin.read_text(encoding="utf-8-sig")
    entete = texte.split("\n", 1)[0].split(";")
    if {"province_pcode", "annee_scolaire"} <= set(entete) and set(RETIREES) & set(entete) \
            and "variable" not in entete:
        return _ecrire_csv(base_deposee(_lire(chemin)))
    return ("﻿" + renommer_texte(texte)).encode("utf-8")


def classeur_depose(source: Path) -> bytes:
    """Classeur coloré de la base apurée, avec les mêmes changements que la base déposée."""
    classeur = load_workbook(source)
    feuille = classeur["base_apuree"]
    entetes = [c.value for c in feuille[1]]
    for indice in sorted((i + 1 for i, v in enumerate(entetes) if v in RETIREES), reverse=True):
        feuille.delete_cols(indice)
    for f in classeur.worksheets:
        for ligne in f.iter_rows():
            for cellule in ligne:
                if isinstance(cellule.value, str) and MOTIF.search(cellule.value):
                    cellule.value = renommer_texte(cellule.value)
    lisez_moi = classeur["Lisez-moi"]
    lisez_moi.cell(row=lisez_moi.max_row + 2, column=1, value=(
        "Version déposée : les colonnes de suivi interne (" + ", ".join(RETIREES) + ") sont retirées, leur "
        "information étant dans les feuilles Journal et Rapport par variable ; les variables du recensement "
        "de 2019, publiées une seule fois et répétées chaque année, portent le suffixe _2019."))
    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()


def dictionnaire_depose() -> pd.DataFrame:
    """Dictionnaire des colonnes de la base déposée (libellé, unité, source, calcul, limites)."""
    d = _lire(config.DONNEES / "03_transformation" / "metadonnees" / "dictionnaire_bases_modele.csv")
    # Table du découpage de 2025 d'abord, puis les autres tables pour les variables propres à la base par sexe.
    d["_ordre"] = d["table"].ne("panel_province_2025")
    d = d.sort_values("_ordre", kind="stable").drop_duplicates("variable").set_index("variable")
    colonnes = base_deposee(_lire(BASE / "base_apuree_par_sexe.csv")).columns
    lignes = []
    for c in dict.fromkeys(list(base_deposee(_lire(BASE / "base_apuree.csv")).columns) + list(colonnes)):
        court = next((k for k, v in RENOMMEES_2019.items() if v == c), c)
        if court in d.index:
            ligne = d.loc[court].to_dict()
        elif c in PAR_SEXE:
            ligne = {"libelle": PAR_SEXE[c][0], "description": PAR_SEXE[c][0] + " (ancienne province, par sexe)",
                     "role": "explicative", "unite": PAR_SEXE[c][1], "type": "décimal", "source": SOURCE_SECONDAIRE}
        else:
            ligne = SEXE if c == "sexe" else {}
        lignes.append({"variable": c, **{k: ligne.get(k, "") for k in
                                         ["libelle", "description", "role", "unite", "type", "calcul", "source",
                                          "limites"]}})
    return pd.DataFrame(lignes)


def _archive_etape(etape: int) -> tuple[bytes, list[str]]:
    """ZIP du dépôt d'une étape ; la base GeoPackage (173 Mo) dépasse la limite et se régénère par le code."""
    dossier = config.DEPOTS / DOSSIERS[etape]
    tampon, ecartes = io.BytesIO(), []
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(dossier.iterdir()):
            if not f.is_file():
                continue
            if f.suffix == ".gpkg":
                ecartes.append(f.name)
            elif f.suffix == ".csv":
                z.writestr(f.name, _table_deposee(f))
            elif f.suffix == ".json" or f.name.endswith("_lisez-moi_v1.txt"):
                z.writestr(f.name, renommer_texte(f.read_text(encoding="utf-8")).encode("utf-8"))
            elif f.suffix == ".xlsx" and "base-apuree" in f.name:
                z.writestr(f.name, classeur_depose(f))
            else:
                z.write(f, f.name)
    return tampon.getvalue(), ecartes


def _archive_code(etape: int) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for element in COMMUN + CODE_ETAPE[etape][2]:
            chemin = config.RACINE / element
            fichiers = [chemin] if chemin.is_file() else sorted(chemin.rglob("*")) if chemin.exists() else []
            for f in fichiers:
                relatif = f.relative_to(config.RACINE)
                if (f.is_file() and not EXCLUS_CODE & set(relatif.parts) and f.name not in FICHIERS_EXCLUS_CODE
                        and f.suffix not in SUFFIXES_EXCLUS_CODE):
                    z.write(f, relatif.as_posix())
    return tampon.getvalue()


def _lisez_moi(fichiers: list[tuple[str, str, str, str]], ecartes: list[str]) -> str:
    lignes = ["# Sentinelle Scolaire : fichiers déposés", "",
              "Défi 1, cartographie et anticipation du risque de décrochage scolaire par province (découpage de "
              "2025), avec prévisions pour 2025-2026, 2026-2027 et 2027-2028.", "",
              f"**Application en ligne :** {LIEN_APPLICATION}", "",
              "Les fichiers sont rangés selon les trois catégories de la plateforme (Code, Données, Documentation) "
              "et nommés selon le modèle du document du challenge, `EQUIPE_ÉTAPE_DÉFI_RÔLE_description_vN` : le nom "
              "de la solution, `SENTINELLE`, tient lieu de nom d'équipe (évaluation à l'aveugle), `D1` désigne le "
              "défi 1 et l'étape renvoie au dépôt (`01_collecte` à `05_interpretation`). Un fichier appartient à "
              "une seule étape ; le code est donc découpé en une archive par étape. Décompressées au même endroit, "
              "les cinq archives de code redonnent le projet complet.", ""]
    for categorie in ["Code", "Données", "Documentation"]:
        lignes += [f"## {categorie}", "", "| Dépôt | Fichier | Contenu |", "|---|---|---|"]
        lignes += [f"| {d} | `{nom}` | {texte} |" for d, c, nom, texte in fichiers if c == categorie]
        lignes.append("")
    lignes += [
        "## Base finale : ce qui change par rapport à la base de travail", "",
        "La base finale compte 47 provinces × 9 années scolaires (2016-2017 à 2024-2025), sans cellule vide. "
        "Le statut de chaque cellule (observée, valeur INSD, imputée, complétée) est dans le classeur et dans "
        "`statut-cellules-base-apuree` (archive de l'étape 03).", "",
        "**Variables du recensement de 2019 (suffixe `_2019`).** Ces indicateurs viennent du RGPH 2019 (INSD, "
        "volume 3) : il n'existe qu'une mesure par province. Elle est répétée sur toutes les années pour servir "
        "de contexte ; elle explique les écarts entre provinces, pas les évolutions dans le temps. Le suffixe le "
        "rend visible dans le nom :", ""]
    lignes += [f"- `{a}` → `{b}`" for a, b in RENOMMEES_2019.items()]
    lignes += ["", "Dans le code, ces variables gardent leur nom court ; le suffixe est ajouté à la préparation "
               "de ce dossier (`python -m sentinelle.soumission`).", "",
               "**Colonnes de suivi retirées** (leur information est dans le journal et le statut des cellules) : "
               + ", ".join(f"`{c}`" for c in RETIREES) + ".", ""]
    if ecartes:
        lignes += ["## Fichier non déposé", "",
                   "La base GeoPackage de l'étape 02 (" + ", ".join(f"`{e}`" for e in ecartes) + ", 173 Mo) "
                   "dépasse la limite de 50 Mo par fichier. Ses tables sont dans l'archive de l'étape 02 au format "
                   "CSV, et `python -m sentinelle.nettoyage` la régénère.", ""]
    lignes += ["## Relancer la chaîne", "",
               "Décompresser les cinq archives de code dans un même dossier, puis suivre le `README.md` : une "
               "commande par étape "
               "(`python -m sentinelle.collecte`, `.nettoyage`, `.transformation`, `.apurement`, `.analyse`, "
               "`.interpretation`), puis l'application (`application/lancer.bat` ou `docker compose up`).", ""]
    return "\n".join(lignes)


def preparer() -> dict[str, list[tuple[str, int]]]:
    # Vide le dossier sans le supprimer : l'explorateur ou OneDrive peut le garder ouvert.
    for ancien in SORTIE.rglob("*") if SORTIE.exists() else []:
        if ancien.is_file():
            ancien.unlink()

    def nom(etape: int, role: str, description: str, extension: str) -> str:
        return f"SENTINELLE_{ETAPES[etape]}_D1_{role}_{description}_v1.{extension}"

    # (étape, catégorie de la plateforme, nom, contenu, description)
    fichiers: list[tuple[int, str, str, bytes, str]] = []
    ecartes = []
    for etape in DOSSIERS:
        role = ROLE_ARCHIVE[etape]
        description, texte, _ = CODE_ETAPE[etape]
        fichiers.append((etape, "Code", nom(etape, role, description, "zip"), _archive_code(etape), texte))
        contenu, e = _archive_etape(etape)
        ecartes += e
        fichiers.append((etape, "Données", nom(etape, role, "depot-donnees-etape", "zip"), contenu,
                         f"Toutes les sorties de l'étape {DOSSIERS[etape]}, avec leur LISEZ-MOI."))

    base, sexe = _lire(BASE / "base_apuree.csv"), _lire(BASE / "base_apuree_par_sexe.csv")
    fichiers += [
        (3, "Données", nom(3, "engineer", "base-finale-province-2016-2025", "csv"), _ecrire_csv(base_deposee(base)),
         f"**Base finale** : {len(base)} lignes (47 provinces × 9 années), {base_deposee(base).shape[1]} colonnes, "
         "aucune cellule vide."),
        (3, "Données", nom(3, "engineer", "base-finale-par-sexe-2016-2025", "csv"), _ecrire_csv(base_deposee(sexe)),
         f"Base finale pour les filles et les garçons : {len(sexe)} lignes, {base_deposee(sexe).shape[1]} colonnes."),
        (3, "Données", nom(3, "engineer", "classeur-base-finale", "xlsx"),
         classeur_depose(BASE / "base_defi1_apuree.xlsx"),
         "Base finale en classeur, cellules colorées selon leur statut, avec journal, rapport par variable et "
         "contrôles."),
        (3, "Données", nom(3, "architect", "dictionnaire-base-finale", "csv"), _ecrire_csv(dictionnaire_depose()),
         "Dictionnaire des colonnes de la base finale : libellé, unité, calcul, source, limites."),
    ]
    prevision = (config.DEPOTS / DOSSIERS[4] /
                 "SENTINELLE_04-analyse_D1_scientist_previsions-tableau-de-bord-province-2025-2028-ensemble_v1.csv")
    fichiers.append((4, "Données", nom(4, "scientist", "previsions-province-2025-2028", "csv"),
                     _table_deposee(prevision),
                     "Prévisions du taux d'abandon 2025-2026 à 2027-2028 par province : intervalle, classe de risque, "
                     "alerte de rupture (version par sexe dans l'archive de l'étape 04)."))
    for etape, role, source, description, texte in DOCUMENTS:
        fichiers.append((etape, "Documentation", nom(etape, role, description, "pdf"), source.read_bytes(), texte))
    lisez_moi = nom(5, "analyst", "lisez-moi-ensemble-des-depots", "md")
    resume = [(DOSSIERS[e], c, n, t) for e, c, n, _, t in fichiers]
    resume.append((DOSSIERS[5], "Documentation", lisez_moi, "Ce fichier : contenu de chaque dépôt."))
    fichiers.append((5, "Documentation", lisez_moi, _lisez_moi(resume, ecartes).encode("utf-8"), ""))

    # Un dossier par catégorie de la plateforme, sans accent ; dans chacun, les fichiers dans l'ordre des étapes.
    for vide in sorted(SORTIE.glob("*"), reverse=True) if SORTIE.exists() else []:
        if vide.is_dir() and not any(vide.iterdir()):
            vide.rmdir()
    bilan: dict[str, list[tuple[str, int]]] = {}
    for etape, categorie, nom_fichier, octets, _ in sorted(fichiers, key=lambda f: (f[0], f[2])):
        assert len(octets) <= LIMITE_OCTETS, (nom_fichier, len(octets))
        dossier = SORTIE / CATEGORIES[categorie]
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / nom_fichier).write_bytes(octets)
        bilan.setdefault(CATEGORIES[categorie], []).append((nom_fichier, len(octets)))
    total = sum(len(f[3]) for f in fichiers)
    assert len(fichiers) <= 20 and total <= 500 * 1024 * 1024, (len(fichiers), total)
    return bilan


if __name__ == "__main__":
    for categorie, liste in preparer().items():
        print(categorie)
        for nom, taille in liste:
            print(f"  {taille / 1e6:6.1f} Mo  {nom}")
