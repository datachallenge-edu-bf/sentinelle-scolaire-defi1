"""Extraction des jeux du catalogue, registre des sources et contrôles de couverture."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from .. import config
from ..lecture import empreinte, fichier_source, infos_manifeste, lire_csv_pack, periode_depuis_nom
from .catalogue import CATALOGUE, PERIODES_CONNUES, SOURCES_ECARTEES, Jeu, Regle

COLONNES_TRACE = ["source_csv_pack", "source_fichier", "source_periode"]
COLONNES_CONTEXTE = ["document", "page", "ligne", "methode", "nb_cellules"]


def _colonnes_cellules(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if re.fullmatch(r"c\d+", c)]


def _texte_par_ligne(df: pd.DataFrame) -> pd.Series:
    cellules = _colonnes_cellules(df)
    texte = df[cellules[0]].str.cat(df[cellules[1:]], sep=" ") if len(cellules) > 1 else df[cellules[0]]
    return texte.str.strip()


def selectionner_pages(df: pd.DataFrame, regle: Regle) -> list[int] | None:
    """Pages retenues par la règle ; None signifie « tout le fichier »."""
    if regle.mode == "tout":
        return None
    if "page" not in df.columns:
        raise ValueError("La sélection par page suppose un CSV issu d'un PDF.")

    pages = pd.to_numeric(df["page"], errors="coerce")
    texte = _texte_par_ligne(df)
    drapeaux = re.IGNORECASE if regle.ignorer_casse else 0

    masque = texte.str.contains(regle.motif, flags=drapeaux, regex=True)
    exclues: set[int] = set()

    if regle.mode == "entete":
        entete = pd.to_numeric(df["ligne"], errors="coerce") <= regle.lignes_entete
        masque &= entete
        if regle.exclure:
            a_exclure = entete & texte.str.contains(regle.exclure, flags=drapeaux, regex=True)
            exclues = set(pages[a_exclure].dropna().astype(int))
    elif regle.exclure:
        masque &= ~texte.str.contains(regle.exclure, flags=drapeaux, regex=True)

    retenues = set(pages[masque].dropna().astype(int)) - exclues

    if regle.continuation and retenues:
        # Une page sans aucun titre de tableau prolonge le tableau de la page précédente.
        titrees = set(pages[texte.str.contains(r"^\s*Tableau", regex=True)].dropna().astype(int))
        derniere = int(pages.max())
        for p in sorted(retenues):
            suivante = p + 1
            while suivante <= derniere and suivante not in titrees and suivante not in retenues:
                retenues.add(suivante)
                suivante += 1

    return sorted(retenues)


def _resoudre_fichiers(jeu: Jeu) -> list[Path]:
    trouves: set[Path] = set()
    for motif in jeu.fichiers:
        if motif.startswith(config.PREFIXE_EXTERNE):
            trouves.update(config.EXTERNES_CSV.glob(motif[len(config.PREFIXE_EXTERNE):]))
        else:
            trouves.update(config.PACK_CSV.glob(motif))
    if jeu.exclure_fichiers:
        trouves = {p for p in trouves if not re.search(jeu.exclure_fichiers, p.name)}
    return sorted(trouves)


def extraire_jeu(jeu: Jeu, date_collecte: str) -> tuple[pd.DataFrame, list[dict]]:
    """Extrait les lignes d'un jeu et décrit chaque fichier source utilisé."""
    morceaux: list[pd.DataFrame] = []
    registre: list[dict] = []

    for csv in _resoudre_fichiers(jeu):
        brut = lire_csv_pack(csv)
        pages = selectionner_pages(brut, jeu.regle)
        extrait = brut if pages is None else brut[pd.to_numeric(brut["page"], errors="coerce").isin(pages)]

        source = fichier_source(csv)
        nom_source = source.name if source else csv.name
        periode = PERIODES_CONNUES.get(nom_source) or periode_depuis_nom(nom_source) or jeu.periode
        relatif = (csv.relative_to(config.DOSSIER_ORGANISATEURS).as_posix() if csv.is_relative_to(config.EXTERNES_CSV)
                   else csv.relative_to(config.PACK_CSV).as_posix())

        extrait = extrait.copy()
        extrait.insert(0, "source_periode", periode)
        extrait.insert(0, "source_fichier", nom_source)
        extrait.insert(0, "source_csv_pack", relatif)
        morceaux.append(extrait)

        registre.append({
            "jeu": jeu.identifiant,
            "libelle": jeu.libelle,
            "theme": jeu.theme,
            "niveau_geo": jeu.niveau_geo,
            "source_fichier": nom_source,
            "source_chemin": source.relative_to(config.DOSSIER_ORGANISATEURS).as_posix() if source else "",
            "source_csv_pack": relatif,
            "periode": periode,
            "regle": jeu.regle.mode if jeu.regle.mode == "tout" else f"{jeu.regle.mode} : {jeu.regle.motif}",
            "pages_retenues": "toutes" if pages is None else _plages(pages),
            "nb_pages": "" if pages is None else len(pages),
            "nb_lignes": len(extrait),
            "sha256_source": empreinte(source) if source else "",
            "sha256_csv_pack": empreinte(csv),
            **infos_manifeste(source.name if source else None),
            "date_collecte": date_collecte,
            "usage": jeu.usage,
        })

    if not morceaux:
        return pd.DataFrame(), registre

    donnees = pd.concat(morceaux, ignore_index=True, sort=False).fillna("")
    return donnees[_ordonner_colonnes(donnees.columns)], registre


def _ordonner_colonnes(colonnes) -> list[str]:
    colonnes = list(colonnes)
    cellules = sorted((c for c in colonnes if re.fullmatch(r"c\d+", c)), key=lambda c: int(c[1:]))
    excel = sorted((c for c in colonnes if re.fullmatch(r"col\d+", c)), key=lambda c: int(c[3:]))
    tete = [c for c in COLONNES_TRACE + COLONNES_CONTEXTE if c in colonnes]
    reste = [c for c in colonnes if c not in tete and c not in cellules and c not in excel]
    return tete + cellules + excel + reste


def _plages(pages: list[int]) -> str:
    """Écrit [3, 4, 5, 9] sous la forme « 3-5, 9 »."""
    if not pages:
        return ""
    plages, debut, prec = [], pages[0], pages[0]
    for p in pages[1:]:
        if p != prec + 1:
            plages.append(f"{debut}-{prec}" if debut != prec else str(debut))
            debut = p
        prec = p
    plages.append(f"{debut}-{prec}" if debut != prec else str(debut))
    return ", ".join(plages)


def extraire_base_principale(date_collecte: str) -> tuple[pd.DataFrame, dict]:
    """Copie brute de chaque feuille de la base DGESS 2016-2025 remise par les organisateurs."""
    chemin = config.BASE_PRINCIPALE
    classeur = load_workbook(chemin, read_only=True, data_only=True)
    morceaux = []
    for feuille in classeur.worksheets:
        lignes = [
            ["" if v is None else str(v) for v in valeurs]
            for valeurs in feuille.iter_rows(values_only=True)
        ]
        if not lignes:
            continue
        largeur = max(len(l) for l in lignes)
        df = pd.DataFrame(
            [l + [""] * (largeur - len(l)) for l in lignes],
            columns=[f"col{i}" for i in range(1, largeur + 1)],
        )
        df.insert(0, "ligne", range(1, len(df) + 1))
        df.insert(0, "feuille", feuille.title)
        morceaux.append(df)
    classeur.close()

    donnees = pd.concat(morceaux, ignore_index=True, sort=False).fillna("")
    donnees.insert(0, "source_periode", "2015-2025")
    donnees.insert(0, "source_fichier", chemin.name)
    donnees = donnees[_ordonner_colonnes(donnees.columns)]

    registre = {
        "jeu": "dgess_base_principale",
        "libelle": "Données statistiques du préscolaire et du primaire 2016-2025 (base principale)",
        "theme": "education",
        "niveau_geo": "region",
        "source_fichier": chemin.name,
        "source_chemin": chemin.relative_to(config.DOSSIER_ORGANISATEURS).as_posix(),
        "source_csv_pack": "",
        "periode": "2015-2025",
        "regle": "toutes les feuilles",
        "pages_retenues": "toutes",
        "nb_pages": "",
        "nb_lignes": len(donnees),
        "sha256_source": empreinte(chemin),
        "sha256_csv_pack": "",
        "producteur": "DGESS / MENAPLN",
        "description_source": "Base principale remise par les organisateurs dans l'espace challenge",
        "url": "",
        "date_collecte": date_collecte,
        "usage": "Séries régionales de référence ; contrôle des agrégats",
    }
    return donnees, registre


def inventaire_fichiers() -> pd.DataFrame:
    """Inventaire de tous les fichiers remis par les organisateurs."""
    lignes = []
    for chemin in config.fichiers_organisateurs():
        relatif = chemin.relative_to(config.DOSSIER_ORGANISATEURS)
        est_csv_pack = chemin.is_relative_to(config.PACK_CSV)
        ligne = {
            "chemin": relatif.as_posix(),
            "dossier": relatif.parent.as_posix(),
            "fichier": chemin.name,
            "format": chemin.suffix.lower().lstrip("."),
            "nature": "extraction CSV du pack" if est_csv_pack else "fichier source",
            "taille_ko": round(chemin.stat().st_size / 1024, 1),
            "sha256": empreinte(chemin),
            "nb_lignes": "",
            "nb_colonnes": "",
            **infos_manifeste(chemin.name),
        }
        if chemin.suffix.lower() == ".csv":
            df = lire_csv_pack(chemin)
            ligne["nb_lignes"], ligne["nb_colonnes"] = df.shape
        lignes.append(ligne)
    return pd.DataFrame(lignes)


def bilan_sources(inventaire: pd.DataFrame, registre: pd.DataFrame) -> pd.DataFrame:
    """Statut de chaque fichier source des organisateurs : retenu, écarté avec motif, ou à examiner."""
    jeux_par_source = registre.groupby("source_chemin")["jeu"].agg(lambda s: ", ".join(sorted(set(s))))
    sources = inventaire[inventaire["nature"] == "fichier source"]

    lignes = []
    for source in sources.itertuples():
        if source.chemin in jeux_par_source.index:
            statut, jeux, motif = "retenue", jeux_par_source[source.chemin], ""
        else:
            motif = next((m for motif_chemin, m in SOURCES_ECARTEES if re.search(motif_chemin, source.chemin)), "")
            statut, jeux = ("écartée" if motif else "à examiner"), ""
        lignes.append({
            "chemin": source.chemin,
            "format": source.format,
            "taille_ko": source.taille_ko,
            "statut": statut,
            "jeux": jeux,
            "motif_exclusion": motif,
        })
    return pd.DataFrame(lignes)


def controle_couverture(registre: pd.DataFrame) -> pd.DataFrame:
    """Signale les fichiers d'un jeu sélectif pour lesquels aucune page n'a été retenue."""
    selectifs = registre[registre["pages_retenues"] != "toutes"].copy()
    selectifs["alerte"] = selectifs["nb_lignes"].astype(int).eq(0).map(
        {True: "aucune page retenue : vérifier le libellé dans le PDF", False: ""}
    )
    return selectifs[["jeu", "source_fichier", "periode", "pages_retenues", "nb_pages", "nb_lignes", "alerte"]]


def ecrire_csv(df: pd.DataFrame, chemin: Path) -> Path:
    chemin = config.verifier_ecriture(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(chemin, sep=config.SEPARATEUR, encoding=config.ENCODAGE_SORTIE, index=False)
    return chemin


def executer_collecte(sortie: Path | None = None, avec_inventaire: bool = True) -> dict[str, pd.DataFrame]:
    """Exécute toute l'étape de collecte et écrit ses sorties.

    Sorties dans ``data/01_collecte`` :
    ``extraits/<jeu>.csv``, ``registre_sources.csv``, ``controle_couverture.csv``,
    ``inventaire_fichiers.csv`` et ``bilan_sources.csv``.
    """
    sortie = Path(sortie or config.SORTIE_COLLECTE)
    date_collecte = date.today().isoformat()
    lignes_registre: list[dict] = []

    for jeu in CATALOGUE:
        donnees, registre = extraire_jeu(jeu, date_collecte)
        lignes_registre.extend(registre)
        if not donnees.empty:
            ecrire_csv(donnees, sortie / "extraits" / f"{jeu.identifiant}.csv")

    base, registre_base = extraire_base_principale(date_collecte)
    lignes_registre.insert(0, registre_base)
    ecrire_csv(base, sortie / "extraits" / "dgess_base_principale.csv")

    registre = pd.DataFrame(lignes_registre)
    couverture = controle_couverture(registre)
    ecrire_csv(registre, sortie / "registre_sources.csv")
    ecrire_csv(couverture, sortie / "controle_couverture.csv")

    resultats = {"registre": registre, "couverture": couverture}
    if avec_inventaire:
        inventaire = inventaire_fichiers()
        bilan = bilan_sources(inventaire, registre)
        ecrire_csv(inventaire, sortie / "inventaire_fichiers.csv")
        ecrire_csv(bilan, sortie / "bilan_sources.csv")
        resultats["inventaire"] = inventaire
        resultats["bilan"] = bilan
    return resultats
