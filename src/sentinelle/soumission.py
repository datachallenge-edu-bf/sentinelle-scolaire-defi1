"""Dossier unique à déposer sur la plateforme : Code, Données, Documentation (20 fichiers au plus, 50 Mo chacun).

Les fichiers viennent des dépôts de chaque étape (``depots/``) et des documents compilés. La version déposée de la
base finale diffère de la base de travail sur deux points, appliqués ici et décrits dans le LISEZ-MOI :

* les variables du recensement de 2019 (une seule mesure, répétée chaque année) portent le suffixe ``_2019`` ;
* les colonnes de suivi interne, déjà couvertes par ``statut_cellules`` et le journal, sont retirées.

Le code garde les noms courts en interne ; la correspondance est la table ``RENOMMEES_2019``.

Lancement, depuis ``defi1_sentinelle`` : ``python -m sentinelle.soumission``
Sortie : ``soumission/`` (ignoré par Git), à téléverser tel quel.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from . import config
from .depots import DOSSIERS

SORTIE = config.RACINE / "soumission"
LIEN_APPLICATION = "https://sentinelle-scolaire-bf.up.railway.app"
LIMITE_OCTETS = 50 * 1024 * 1024

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
CODE = ["src", "notebooks", "tests", "application", "README.md", "requirements.txt", "pyproject.toml",
        ".gitignore", ".gitattributes", ".dockerignore", "data/LISEZ-MOI.md",
        # Sorties légères que l'application relit : elle démarre sans relancer toute la chaîne.
        "data/02_nettoyage/contours_web", "data/03_transformation/base_apuree",
        "data/03_transformation/dictionnaire_variables_modele.csv",
        "data/03_transformation/metadonnees/dictionnaire_bases_modele.csv", "data/04_analyse"]
EXCLUS_CODE = {"node_modules", ".next", "deploiement", "__pycache__", ".pytest_cache", ".ruff_cache",
               ".ipynb_checkpoints"}
FICHIERS_EXCLUS_CODE = {".env", "next-env.d.ts", "tsconfig.tsbuildinfo"}
DOCUMENTS = [
    (config.RACINE / "docs/documentation/documentation_sentinelle.pdf", "documentation-solution",
     "**Documentation de la solution** (format IJCAI, 14 pages) : données, méthode, performances, prévisions, "
     "application, limites."),
    (config.RACINE / "application/web/public/guide_sentinelle.pdf", "guide-utilisation-tableau-de-bord",
     "Guide d'utilisation du tableau de bord, écran par écran."),
    (config.RACINE / "docs/methodologie/methodologie_donnees.pdf", "methodologie-collecte-nettoyage-donnees",
     "Document technique : collecte, nettoyage et contrôle des données."),
    (config.RACINE / "docs/methodologie/passage_decoupage_2025.pdf", "methodologie-passage-decoupage-2025",
     "Document technique : passage des données au découpage administratif de 2025."),
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


def _archive_code() -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for element in CODE:
            chemin = config.RACINE / element
            fichiers = [chemin] if chemin.is_file() else sorted(chemin.rglob("*")) if chemin.exists() else []
            for f in fichiers:
                relatif = f.relative_to(config.RACINE)
                if f.is_file() and not EXCLUS_CODE & set(relatif.parts) and f.name not in FICHIERS_EXCLUS_CODE:
                    z.write(f, relatif.as_posix())
    return tampon.getvalue()


def _lisez_moi(fichiers: dict[str, list[tuple[str, str]]], ecartes: list[str]) -> str:
    lignes = ["# Sentinelle Scolaire : fichiers déposés", "",
              "Défi 1, cartographie et anticipation du risque de décrochage scolaire par province (découpage de "
              "2025), avec prévisions pour 2025-2026, 2026-2027 et 2027-2028.", "",
              f"**Application en ligne :** {LIEN_APPLICATION}", "",
              "Les noms suivent la convention du challenge : `SENTINELLE_ÉTAPE_D1_RÔLE_description_vN`.", ""]
    for categorie, liste in fichiers.items():
        lignes += [f"## {categorie}", "", "| Fichier | Contenu |", "|---|---|"]
        lignes += [f"| `{nom}` | {texte} |" for nom, texte in liste]
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
               "Voir le `README.md` de l'archive de code : une commande par étape "
               "(`python -m sentinelle.collecte`, `.nettoyage`, `.transformation`, `.apurement`, `.analyse`, "
               "`.interpretation`), puis l'application (`application/lancer.bat` ou `docker compose up`).", ""]
    return "\n".join(lignes)


def preparer() -> dict[str, list[tuple[str, str, int]]]:
    # Vide le dossier sans le supprimer : l'explorateur ou OneDrive peut le garder ouvert.
    for ancien in SORTIE.rglob("*") if SORTIE.exists() else []:
        if ancien.is_file():
            ancien.unlink()
    contenus: dict[str, list[tuple[str, bytes, str]]] = {"Code": [], "Données": [], "Documentation": []}

    contenus["Code"].append(("SENTINELLE_D1_code-complet-solution-et-application_v1.zip", _archive_code(),
                             "Tout le code : chaîne `src/sentinelle` (étapes 01 à 05), notebooks exécutés, tests, "
                             "application (API FastAPI et site Next.js, Dockerfile) et sorties légères qu'elle relit."))

    base, sexe = _lire(BASE / "base_apuree.csv"), _lire(BASE / "base_apuree_par_sexe.csv")
    t03, t04 = "SENTINELLE_03-transformation_D1_engineer_", "SENTINELLE_04-analyse_D1_scientist_"
    depot04 = config.DEPOTS / DOSSIERS[4]
    donnees = [
        (f"{t03}base-finale-province-2016-2025_v1.csv", _ecrire_csv(base_deposee(base)),
         f"**Base finale** : {len(base)} lignes (47 provinces × 9 années), {base_deposee(base).shape[1]} colonnes, "
         "aucune cellule vide."),
        (f"{t03}base-finale-par-sexe-2016-2025_v1.csv", _ecrire_csv(base_deposee(sexe)),
         f"Base finale pour les filles et les garçons : {len(sexe)} lignes, {base_deposee(sexe).shape[1]} colonnes."),
        (f"{t03}classeur-base-finale_v1.xlsx", classeur_depose(BASE / "base_defi1_apuree.xlsx"),
         "Base finale en classeur, cellules colorées selon leur statut, avec journal, rapport par variable et "
         "contrôles."),
        (f"{t03}dictionnaire-base-finale_v1.csv", _ecrire_csv(dictionnaire_depose()),
         "Dictionnaire des colonnes de la base finale : libellé, unité, calcul, source, limites."),
    ]
    for population, texte in [("ensemble", "toutes les provinces"), ("par-sexe", "filles et garçons")]:
        f = depot04 / f"{t04}previsions-tableau-de-bord-province-2025-2028-{population}_v1.csv"
        donnees.append((f"{t04}previsions-province-2025-2028-{population}_v1.csv", _table_deposee(f),
                        f"Prévisions du taux d'abandon 2025-2026 à 2027-2028 ({texte}) : intervalle, classe de "
                        "risque, alerte de rupture."))
    ecartes = []
    for etape, dossier in DOSSIERS.items():
        contenu, e = _archive_etape(etape)
        ecartes += e
        donnees.append((f"SENTINELLE_{dossier.replace('_', '-', 1)}_D1_{ROLE_ARCHIVE[etape]}_depot-complet-etape_v1.zip",
                        contenu, f"Dépôt complet de l'étape {dossier} (avec son LISEZ-MOI)."))
    contenus["Données"] = donnees

    for source, description, texte in DOCUMENTS:
        contenus["Documentation"].append((f"SENTINELLE_D1_{description}_v1.pdf", source.read_bytes(), texte))
    resume = {c: [(n, t) for n, _, t in liste] for c, liste in contenus.items()}
    contenus["Documentation"].append(("SENTINELLE_D1_lisez-moi_v1.md",
                                      _lisez_moi(resume, ecartes).encode("utf-8"), "Ce fichier."))

    bilan = {}
    for categorie, liste in contenus.items():
        dossier = SORTIE / categorie
        dossier.mkdir(parents=True, exist_ok=True)
        bilan[categorie] = []
        for nom, octets, _ in liste:
            assert len(octets) <= LIMITE_OCTETS, (nom, len(octets))
            (dossier / nom).write_bytes(octets)
            bilan[categorie].append((nom, len(octets)))
    nombre = sum(len(v) for v in bilan.values())
    total = sum(t for v in bilan.values() for _, t in v)
    assert nombre <= 20 and total <= 500 * 1024 * 1024, (nombre, total)
    return bilan


if __name__ == "__main__":
    for categorie, liste in preparer().items():
        print(categorie)
        for nom, taille in liste:
            print(f"  {taille / 1e6:6.1f} Mo  {nom}")
