"""Lecture des sorties de l'analyse (étape 04) et des contours, une seule fois au démarrage.

L'API ne recalcule aucune prévision : elle sert les tableaux produits par
``sentinelle.analyse.executer_modelisation`` et les modèles sauvegardés dans
``data/04_analyse/modeles/``. Seul le simulateur appelle un modèle (l'elastic net des effets chiffrés).
"""

from __future__ import annotations

import json
import math
import sys
from functools import cached_property
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[2]
DONNEES = RACINE / "data"
MODELISATION = DONNEES / "04_analyse" / "modelisation"
MODELES = DONNEES / "04_analyse" / "modeles"
BASE = DONNEES / "03_transformation" / "base_apuree"
CONTOURS = DONNEES / "02_nettoyage" / "contours_web"

sys.path.insert(0, str(RACINE / "src"))
from sentinelle.analyse import sauvegarde  # noqa: E402
from sentinelle.analyse.libelles import libelle  # noqa: E402

SEUIL_RUPTURE = 0.30
POPULATIONS = {"ensemble": "Ensemble", "F": "Filles", "G": "Garçons"}
ANNEE_PREVUE = "2025-2026"
ANNEES_PROJETEES = ["2026-2027", "2027-2028"]
LIBELLES_SUPPLEMENTAIRES = {"fille": "être une fille"}


def lire(nom: str, dossier: Path = MODELISATION) -> pd.DataFrame:
    return pd.read_csv(dossier / f"{nom}.csv", sep=";", encoding="utf-8-sig")


def nom_variable(v: str) -> str:
    return LIBELLES_SUPPLEMENTAIRES.get(v, libelle(v))


def propre(valeur):
    """Valeur sérialisable en JSON (NaN et infinis deviennent null)."""
    if isinstance(valeur, dict):
        return {str(k): propre(v) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [propre(v) for v in valeur]
    if isinstance(valeur, (np.bool_, bool)):
        return bool(valeur)
    if isinstance(valeur, (np.integer,)):
        return int(valeur)
    if isinstance(valeur, (np.floating, float)):
        return None if not math.isfinite(valeur) else float(valeur)
    return valeur


def enregistrements(t: pd.DataFrame) -> list[dict]:
    return [propre(r) for r in t.to_dict("records")]


def logit(taux: float) -> float:
    p = min(max(taux, 0.5), 99.5) / 100
    return math.log(p / (1 - p))


def taux(z: float) -> float:
    return 100 / (1 + math.exp(-z))


def fr(x: float, decimales: int = 1) -> str:
    """Nombre écrit à la française (virgule décimale)."""
    return f"{x:.{decimales}f}".replace(".", ",")


class Donnees:
    """Toutes les tables utiles au tableau de bord, chargées à la première demande."""

    def __init__(self):
        self._cache: dict = {}

    @cached_property
    def tableau_ensemble(self) -> pd.DataFrame:
        return lire("tableau_de_bord_ensemble")

    @cached_property
    def tableau_sexe(self) -> pd.DataFrame:
        return lire("tableau_de_bord_sexe")

    def tableau(self, population: str) -> pd.DataFrame:
        if population == "ensemble":
            return self.tableau_ensemble
        return self.tableau_sexe[self.tableau_sexe["sexe"] == population].reset_index(drop=True)

    @cached_property
    def modeles(self) -> dict:
        return {nom: sauvegarde.charger(MODELES, nom) for nom in ["ensemble", "sexe"]}

    def fiche(self, population: str) -> dict:
        return self.modeles["ensemble" if population == "ensemble" else "sexe"]["fiche"]

    @cached_property
    def base(self) -> pd.DataFrame:
        return pd.read_csv(BASE / "base_apuree.csv", sep=";", encoding="utf-8-sig")

    @cached_property
    def base_sexe(self) -> pd.DataFrame:
        return pd.read_csv(BASE / "base_apuree_par_sexe.csv", sep=";", encoding="utf-8-sig")

    @cached_property
    def provinces(self) -> gpd.GeoDataFrame:
        return gpd.read_file(CONTOURS / "province.geojson")

    @cached_property
    def regions(self) -> gpd.GeoDataFrame:
        return gpd.read_file(CONTOURS / "region.geojson")

    @staticmethod
    def points_etiquettes(g: gpd.GeoDataFrame, cle: str) -> dict:
        points = g.geometry.representative_point()
        return {k: [round(p.x, 4), round(p.y, 4)] for k, p in zip(g[cle], points)}

    @cached_property
    def poids(self) -> pd.Series:
        """Effectif du primaire de la dernière année, pour les moyennes régionales pondérées."""
        b = self.base[self.base["annee_scolaire"] == self.base["annee_scolaire"].max()]
        return b.set_index("province_pcode")["eleves_primaire"]

    # Explication -----------------------------------------------------------------------------------

    def jeu(self, population: str) -> str:
        return "ensemble" if population == "ensemble" else "sexe"

    def explication(self, nom: str, population: str) -> pd.DataFrame:
        t = lire(f"explication_{nom}_{self.jeu(population)}")
        if population != "ensemble" and "sexe" in t.columns:
            t = t[t["sexe"] == population]
        return t.reset_index(drop=True)

    def valeur_de_base(self, population: str) -> float:
        return float(lire(f"explication_valeur_de_base_{self.jeu(population)}").iloc[0, 0])

    def attendu_hors_echantillon(self, population: str) -> pd.DataFrame:
        """Niveau attendu de chaque province d'après ses caractéristiques, prédit par un LightGBM qui ne l'a pas
        vue (validation croisée par groupes de provinces, mêmes réglages et variables que le modèle sauvegardé)."""
        import lightgbm as lgb
        from sklearn.model_selection import GroupKFold
        from sentinelle.analyse.explication import PARAMETRES_LGB, PLIS_GROUPES

        cle = ("attendu", self.jeu(population))
        if cle not in self._cache:
            t = lire(f"explication_valeurs_{self.jeu(population)}").dropna(subset=["niveau_habituel_observe"])
            t = t.reset_index(drop=True)
            variables = self.modeles[self.jeu(population)]["explication_lightgbm"]["variables"]
            x, y = t[variables], t["niveau_habituel_observe"]
            attendu = pd.Series(np.nan, index=t.index)
            for a, b in GroupKFold(PLIS_GROUPES).split(x, y, t["province_pcode"]):
                m = lgb.LGBMRegressor(**PARAMETRES_LGB).fit(x.iloc[a], y.iloc[a])
                attendu.iloc[b] = m.predict(x.iloc[b])
            t["attendu"] = attendu
            t["ecart"] = t["niveau_habituel_observe"] - t["attendu"]
            self._cache[cle] = t
        t = self._cache[cle]
        if population != "ensemble":
            t = t[t["sexe"] == population]
        return t

    @cached_property
    def contributions_alerte(self) -> pd.DataFrame:
        return lire("contributions_alerte_rupture")

    @cached_property
    def evaluation_alerte(self) -> pd.DataFrame:
        return lire("evaluation_alerte_rupture")

    def erreur_test_final(self, population: str, modele: str | None = None) -> float:
        s = lire(f"synthese_modeles_{self.jeu(population)}")
        modele = modele or self.fiche(population)["prevision"]["modele_retenu"]
        ligne = s[(s["role"] == "test final") & (s["modele"] == modele) & (s["horizon"] == 1)]
        return float(ligne["erreur_absolue_moyenne"].iloc[0])

    # Historique ------------------------------------------------------------------------------------

    def historique(self, pcode: str, population: str) -> list[dict]:
        """Taux d'abandon de chaque année cible : l'abandon « précédent » de la ligne t est mesuré entre t-1 et t,
        comme la cible des modèles (année cible t)."""
        b = self.base if population == "ensemble" else self.base_sexe[self.base_sexe["sexe"] == population]
        b = b[b["province_pcode"] == pcode].sort_values("annee_scolaire")
        lignes = []
        for _, r in b.iterrows():
            valeur = r["abandon_primaire_precedent"]
            if pd.isna(valeur):
                continue
            evolution = r.get("evolution_eleves_primaire", np.nan)
            lignes.append({"annee": r["annee_scolaire"], "taux": round(float(valeur), 2),
                           "observe": bool(r["cible_observee"]),
                           "rupture": bool(pd.notna(evolution) and abs(evolution) > SEUIL_RUPTURE)})
        return lignes

    # Simulateur ------------------------------------------------------------------------------------

    @cached_property
    def moyennes_provinces(self) -> pd.DataFrame:
        variables = self.modeles["ensemble"]["explication_elastic_net"]["variables"]
        return self.base.groupby("province_pcode")[variables].mean()


DONNEES_APPLI = Donnees()
