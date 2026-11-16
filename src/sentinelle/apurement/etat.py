"""État de la base au fil de l'apurement : valeurs, journal de chaque cellule modifiée, statut des cellules."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Statut d'une cellule dans la base apurée (et couleur dans le classeur).
OBSERVEE = "observée"
SOURCE_INSD = "valeur publiée INSD"
IMPUTEE = "imputée"
COMPLETEE = "complétée à l'étape 3"

SCINDEES = ["Djelgodji", "Karo-Peli", "Dyamongou", "Gobnangou"]


def _valeur(v):
    if isinstance(v, (float, np.floating)) and np.isnan(v):
        return ""
    return v


@dataclass
class Apurement:
    base: pd.DataFrame
    journal: list[dict] = field(default_factory=list)
    statut: dict[tuple[int, str], str] = field(default_factory=dict)
    imputations_par_ligne: dict[int, int] = field(default_factory=dict)
    statut_ligne: dict[int, str] = field(default_factory=dict)

    @property
    def scindee(self) -> pd.Series:
        return self.base["methode_passage"].str.startswith("province scindée")

    def ligne(self, province: str, annee: str) -> int:
        return self.base.index[(self.base["province_nom"] == province) & (self.base["annee_scolaire"] == annee)][0]

    def noter(self, etape: int, i: int, variable: str, avant, apres, methode: str, detail: str = "",
              nature: str = "imputation") -> None:
        ligne = self.base.loc[i]
        self.journal.append({"etape": etape, "nature": nature, "province_nom": ligne["province_nom"],
                             "province_pcode": ligne["province_pcode"], "annee_scolaire": ligne["annee_scolaire"],
                             "variable": variable, "valeur_avant": _valeur(avant), "valeur_apres": _valeur(apres),
                             "methode": methode, "detail": detail, "_i": i})

    def journal_table(self) -> pd.DataFrame:
        return pd.DataFrame(self.journal).drop(columns="_i")
