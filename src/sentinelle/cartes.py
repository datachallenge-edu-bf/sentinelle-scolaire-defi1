"""Cartes statiques de l'abandon scolaire.

Palette divergente : rouge pour l'abandon, du clair au foncé ; bleu pour les
valeurs négatives (arrivées nettes d'élèves, par exemple de familles déplacées) ;
gris neutre autour de zéro. Les classes sont fixes pour que les années restent
comparables entre elles.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

from . import config

SURFACE = "#fcfcfb"
ENCRE = "#0b0b0b"
ENCRE_SECONDAIRE = "#52514e"
LIMITE = "#ffffff"

CLASSES = [-100, 0, 2.5, 5, 10, 15, 20, 100]
COULEURS = ["#3987e5", "#f0efec", "#f6c9c3", "#ee9a8f", "#de6455", "#b8342a", "#7d1a14"]
LIBELLES = ["Arrivées nettes (< 0 %)", "0 à 2,5 %", "2,5 à 5 %", "5 à 10 %", "10 à 15 %", "15 à 20 %", "20 % et plus"]


def _style(ax: plt.Axes) -> None:
    ax.set_axis_off()
    ax.set_facecolor(SURFACE)


def _legende(fig: plt.Figure, hachures: bool) -> None:
    elements = [Patch(facecolor=c, edgecolor="#bdbcb6", linewidth=0.5, label=l) for c, l in zip(COULEURS, LIBELLES)]
    if hachures:
        elements.append(Patch(facecolor="white", edgecolor="#52514e", hatch="////", linewidth=0.5,
                              label="Province scindée en 2025 : taux de l'ancienne province"))
    fig.legend(handles=elements, loc="lower center", ncol=4, frameon=False, fontsize=8.5,
               labelcolor=ENCRE_SECONDAIRE, handlelength=1.6, columnspacing=1.4)


def carte_abandon(couche: gpd.GeoDataFrame, valeurs: pd.Series, titre: str, sous_titre: str, source: str,
                  chemin: Path, contours_regions: gpd.GeoDataFrame | None = None,
                  etiquettes: int = 6, nom: str = "province_nom") -> Path:
    """Carte choroplèthe d'un taux d'abandon (en %), avec les plus fortes valeurs étiquetées."""
    donnees = couche.copy()
    donnees["taux"] = valeurs.reindex(donnees.index).values
    cmap = ListedColormap(COULEURS)
    norme = BoundaryNorm(CLASSES, cmap.N)

    fig, ax = plt.subplots(figsize=(9, 8.2), facecolor=SURFACE)
    _style(ax)
    donnees.plot(ax=ax, column="taux", cmap=cmap, norm=norme, edgecolor=LIMITE, linewidth=0.6,
                 missing_kwds={"color": "#e2e1dc", "hatch": "...", "label": "Sans donnée"})
    hachures = "province_ancienne_partagee" in donnees and donnees["province_ancienne_partagee"].any()
    if hachures:
        donnees[donnees["province_ancienne_partagee"]].plot(
            ax=ax, facecolor="none", edgecolor="#52514e", hatch="////", linewidth=0.0)
    if contours_regions is not None:
        contours_regions.boundary.plot(ax=ax, color="#52514e", linewidth=1.1)

    for _, ligne in donnees.nlargest(etiquettes, "taux").iterrows():
        point = ligne.geometry.representative_point()
        ax.annotate(f"{ligne[nom]}\n{ligne['taux']:.1f} %".replace(".", ","), (point.x, point.y),
                    ha="center", va="center", fontsize=7.5, color=ENCRE,
                    bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "none", "alpha": 0.85})

    fig.text(0.04, 0.95, titre, fontsize=14, fontweight="bold", color=ENCRE, ha="left")
    fig.text(0.04, 0.915, sous_titre, fontsize=9.5, color=ENCRE_SECONDAIRE, ha="left")
    fig.text(0.04, 0.115, source, fontsize=7.5, color=ENCRE_SECONDAIRE, ha="left", wrap=True)
    _legende(fig, hachures)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.9, bottom=0.17)

    chemin = config.verifier_ecriture(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(chemin, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return chemin


def petits_multiples(couche: gpd.GeoDataFrame, taux: pd.DataFrame, colonne_periode: str, titre: str,
                     source: str, chemin: Path, colonnes: int = 4) -> Path:
    """Une petite carte par période, mêmes classes de couleur pour toutes."""
    periodes = sorted(taux[colonne_periode].unique())
    lignes = -(-len(periodes) // colonnes)
    cmap = ListedColormap(COULEURS)
    norme = BoundaryNorm(CLASSES, cmap.N)

    fig, axes = plt.subplots(lignes, colonnes, figsize=(3.2 * colonnes, 3.1 * lignes + 1.4), facecolor=SURFACE)
    for ax in axes.flat:
        _style(ax)
    for ax, periode in zip(axes.flat, periodes):
        valeurs = taux[taux[colonne_periode] == periode].set_index("entite_pcode")["taux_abandon"]
        d = couche.assign(taux=couche.index.map(valeurs))
        d.plot(ax=ax, column="taux", cmap=cmap, norm=norme, edgecolor=LIMITE, linewidth=0.4,
               missing_kwds={"color": "#e2e1dc"})
        ax.set_title(periode.replace("-", " → "), fontsize=9.5, color=ENCRE)

    fig.text(0.02, 0.975, titre, fontsize=13, fontweight="bold", color=ENCRE, ha="left", va="top")
    fig.text(0.02, 0.03, source, fontsize=7.5, color=ENCRE_SECONDAIRE, ha="left")
    _legende(fig, hachures=False)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.9, bottom=0.14, wspace=0.02, hspace=0.12)
    fig.legends[0].set_bbox_to_anchor((0.5, 0.055))

    chemin = config.verifier_ecriture(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(chemin, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return chemin
