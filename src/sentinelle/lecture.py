"""Lecture des fichiers du Data Pack et des métadonnées associées."""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import config

MOIS = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "aout": 8, "août": 8, "septembre": 9, "octobre": 10,
    "novembre": 11, "decembre": 12, "décembre": 12,
}


def lire_csv_pack(chemin: Path) -> pd.DataFrame:
    """Lit un CSV du Data Pack sans aucune conversion : toutes les cellules restent du texte."""
    return _lire_csv_pack(str(Path(chemin).resolve())).copy()


@lru_cache(maxsize=64)
def _lire_csv_pack(chemin: str) -> pd.DataFrame:
    return pd.read_csv(
        chemin,
        sep=";",
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=False,
    )


def empreinte(chemin: Path) -> str:
    """Empreinte SHA-256 d'un fichier, pour tracer la version exacte utilisée."""
    chemin = Path(chemin)
    etat = chemin.stat()
    return _empreinte(str(chemin.resolve()), etat.st_size, etat.st_mtime_ns)


@lru_cache(maxsize=None)
def _empreinte(chemin: str, taille: int, modification: int, taille_bloc: int = 1 << 20) -> str:
    # La taille et la date de modification font partie de la clé : un fichier modifié est recalculé.
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        while bloc := f.read(taille_bloc):
            h.update(bloc)
    return h.hexdigest()


@lru_cache(maxsize=1)
def manifeste() -> pd.DataFrame:
    """Manifeste des téléchargements du Data Pack, indexé par nom de fichier."""
    m = lire_csv_pack(config.MANIFESTE)
    return m.drop_duplicates("fichier").set_index("fichier")


def fichier_source(csv_pack: Path) -> Path | None:
    """Retrouve le fichier d'origine (PDF, XLSX...) dont un CSV du pack est l'extraction."""
    relatif = csv_pack.relative_to(config.PACK_CSV)
    dossier = config.DATA_PACK / relatif.parent
    if not dossier.is_dir():
        return None
    racine_nom = csv_pack.stem.split("__")[0]
    candidats = sorted(
        p for p in dossier.iterdir()
        if p.is_file() and p.stem == racine_nom and p.suffix.lower() != ".csv"
    )
    if candidats:
        return candidats[0]
    natif = dossier / csv_pack.name
    return natif if natif.exists() else None


def infos_manifeste(nom_fichier: str | None) -> dict[str, str]:
    """Producteur, description et URL d'origine d'un fichier, d'après le manifeste."""
    vide = {"producteur": "", "description_source": "", "url": ""}
    if not nom_fichier:
        return vide
    m = manifeste()
    if nom_fichier not in m.index:
        return vide
    ligne = m.loc[nom_fichier]
    return {
        "producteur": ligne.get("source", ""),
        "description_source": ligne.get("description", ""),
        "url": ligne.get("url", ""),
    }


def periode_depuis_nom(nom: str) -> str:
    """Déduit la période couverte à partir du nom de fichier.

    Renvoie « AAAA-AAAA » pour une année scolaire, « AAAA-MM » ou « AAAA-MM-JJ »
    pour un rapport daté, « AAAA » pour une année seule, et une chaîne vide sinon.
    """
    texte = nom.lower()

    if m := re.search(r"(20\d{2})[_-](20\d{2})", texte):
        return f"{m.group(1)}-{m.group(2)}"

    if m := re.search(r"(?<!\d)(\d{1,2})[-_](\d{1,2})[-_](20\d{2})(?!\d)", texte):
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"

    texte = re.sub(r"(?<![a-z])d(?=(avril|aout|août|octobre))", "", texte)  # « davril » : « d'avril » sans apostrophe

    if m := re.search(r"(\d{1,2})[-_]([a-zéû]+)[-_](20\d{2})", texte):
        if m.group(2) in MOIS:
            return f"{m.group(3)}-{MOIS[m.group(2)]:02d}-{int(m.group(1)):02d}"

    for mot, numero in MOIS.items():
        if re.search(rf"(?<![a-z]){mot}(?![a-z])", texte):
            if annee := re.search(r"20\d{2}", texte):
                return f"{annee.group(0)}-{numero:02d}"

    if m := re.search(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)", texte):
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if m := re.search(r"(?<!\d)(\d{2})(\d{2})(20\d{2})(?!\d)", texte):
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    if m := re.search(r"(?<!\d)(\d{2})_(\d{2})_(20\d{2})(?!\d)", texte):
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    if m := re.search(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)", texte):
        return f"20{m.group(3)}-{m.group(2)}-{m.group(1)}"

    if m := re.search(r"(?<!\d)(20\d{2})(?!\d)", texte):
        return m.group(1)
    return ""
