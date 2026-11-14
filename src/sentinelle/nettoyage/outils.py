"""Outils communs au nettoyage : lecture des extraits, nombres, noms, journal."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import config

_NOMBRE = re.compile(r"^-?\d{1,3}(?:[   ]\d{3})+(?:[,.]\d+)?$|^-?\d+(?:[,.]\d+)?$")
_ANNEE_SCOLAIRE = re.compile(r"^(20\d{2})\s*[/-]\s*(20\d{2})$")


def lire_extrait(identifiant: str) -> pd.DataFrame:
    """Lit un extrait brut produit par l'étape de collecte."""
    return pd.read_csv(
        config.SORTIE_COLLECTE / "extraits" / f"{identifiant}.csv",
        sep=config.SEPARATEUR,
        dtype=str,
        encoding=config.ENCODAGE_SORTIE,
        keep_default_na=False,
    )


def colonnes_cellules(df: pd.DataFrame) -> list[str]:
    return sorted((c for c in df.columns if re.fullmatch(r"c\d+", c)), key=lambda c: int(c[1:]))


def cellules(ligne: pd.Series, colonnes: list[str]) -> list[str]:
    """Cellules non vides d'une ligne extraite d'un PDF, dans l'ordre."""
    return [v.strip() for v in (ligne[c] for c in colonnes) if v and v.strip()]


def est_nombre(texte: str) -> bool:
    return bool(_NOMBRE.match(texte.strip()))


def en_nombre(texte: str) -> float:
    """Convertit « 1 578 », « 99,4 » ou « 15,47 » en nombre ; NaN si le texte n'est pas un nombre."""
    texte = texte.strip()
    if not est_nombre(texte):
        return np.nan
    return float(re.sub(r"[   ]", "", texte).replace(",", "."))


def annee_scolaire(texte: str) -> str | None:
    """« 2024/2025 » devient « 2024-2025 » ; None si le texte n'est pas une année scolaire.

    Une année répétée dans la même cellule (« 2008/2009 2008/2009 ») est acceptée.
    """
    morceaux = set(texte.split())
    if len(morceaux) != 1:
        return None
    m = _ANNEE_SCOLAIRE.match(morceaux.pop())
    return f"{m.group(1)}-{m.group(2)}" if m else None


def normaliser_nom(texte: str) -> str:
    """Majuscules, sans accent, sans espace ni ponctuation : « Centre - Est » devient « CENTREEST »."""
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", sans_accent.upper())


@dataclass
class Journal:
    """Journal des opérations de nettoyage : chaque correction ou anomalie y est consignée."""

    lignes: list[dict] = field(default_factory=list)

    def noter(self, table: str, operation: str, motif: str, *, source: str = "", page: str = "",
              ligne: str = "", avant: str = "", apres: str = "") -> None:
        self.lignes.append({
            "table": table,
            "operation": operation,
            "motif": motif,
            "source_fichier": source,
            "page": page,
            "ligne": ligne,
            "valeur_avant": avant,
            "valeur_apres": apres,
        })

    def table(self) -> pd.DataFrame:
        colonnes = ["table", "operation", "motif", "source_fichier", "page", "ligne", "valeur_avant", "valeur_apres"]
        return pd.DataFrame(self.lignes, columns=colonnes)
