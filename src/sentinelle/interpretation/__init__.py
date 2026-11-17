"""Étape 05 : interprétation et visualisation.

Entrée : sorties de l'étape 04 (``data/04_analyse/``) et application ``application/`` (API et tableau de bord).
Sortie : ``data/05_interpretation/`` :

- ``indicateurs_cles_province.csv`` et ``indicateurs_cles_region.csv`` : taux observé 2024-2025, taux prévus
  2025-2026 à 2027-2028 avec intervalle et classe, nombre estimé d'élèves qui abandonnent, alerte de rupture,
  principaux facteurs ;
- ``carte_alerte_2025_2026.png`` : carte des classes de risque et des alertes de rupture ;
- ``rapports/`` : rapport national, rapports des 17 régions, fiches des 47 provinces (PDF) ;
- ``guide_sentinelle.pdf`` : guide d'utilisation du tableau de bord ;
- ``application_sentinelle_source.zip`` : code du tableau de bord (API FastAPI, site Next.js) pour le relancer.

Les rapports et la carte sont produits par le même code que le tableau de bord (``application/api``), pour que
les chiffres soient identiques partout.
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .. import config

SORTIE = config.DONNEES / "05_interpretation"
APPLICATION = config.RACINE / "application"
LIEN_EN_LIGNE = "https://sentinelle-scolaire-bf.up.railway.app"
EXCLUS_APPLICATION = {"node_modules", ".next", "deploiement", "__pycache__", ".env"}


def _api():
    """Modules de l'API du tableau de bord (rapports, données), chargés depuis ``application/api``."""
    chemin = str(APPLICATION / "api")
    if chemin not in sys.path:
        sys.path.insert(0, chemin)
    import main  # noqa: F401  (enregistre les points d'accès utilisés par les rapports)
    import rapport
    from donnees import DONNEES_APPLI
    return main, rapport, DONNEES_APPLI


def indicateurs_cles(population: str = "ensemble") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tables des indicateurs clés par province et par région, pour les quatre années affichées."""
    main, _, donnees = _api()
    n = main.national(population)
    tableau = donnees.tableau(population).set_index("province_pcode")
    lignes = []
    for p in n["provinces"]:
        ligne = {"province_pcode": p["pcode"], "province": p["province"], "region": p["region"],
                 "eleves_primaire_2024_2025": p["poids"]}
        for s in p["serie"]:
            a = s["annee"].replace("-", "_")
            ligne[f"taux_{a}"] = s["taux"]
            if s["bas"] is not None:
                ligne[f"borne_basse_80_{a}"] = s["bas"]
                ligne[f"borne_haute_80_{a}"] = s["haut"]
            ligne[f"classe_{a}"] = s["classe"]
            # Nombre estimé d'élèves qui abandonnent : taux × effectif du primaire de 2024-2025.
            ligne[f"abandons_estimes_{a}"] = round((s["taux"] or 0) / 100 * (p["poids"] or 0))
        ligne.update({"score_rupture": p["score_rupture"], "risque_de_rupture": p["rupture"],
                      "facteur_1": tableau.loc[p["pcode"], "facteur_1"], "facteur_2": tableau.loc[p["pcode"], "facteur_2"],
                      "facteur_3": tableau.loc[p["pcode"], "facteur_3"],
                      "frein_principal": tableau.loc[p["pcode"], "frein_principal"]})
        lignes.append(ligne)
    provinces = pd.DataFrame(lignes).sort_values("taux_2025_2026", ascending=False)

    annees = [s["annee"].replace("-", "_") for s in n["provinces"][0]["serie"]]
    regions = []
    for region, g in provinces.groupby("region"):
        poids = g["eleves_primaire_2024_2025"].fillna(0)
        r = {"region": region, "provinces": len(g), "eleves_primaire_2024_2025": int(poids.sum())}
        for a in annees:
            r[f"taux_pondere_{a}"] = round(float(np.average(g[f"taux_{a}"], weights=poids)), 2)
            r[f"abandons_estimes_{a}"] = int(g[f"abandons_estimes_{a}"].sum())
            r[f"provinces_risque_eleve_{a}"] = int((g[f"classe_{a}"] == "élevé").sum())
        r["alertes_rupture"] = int((g["risque_de_rupture"] == "élevé").sum())
        regions.append(r)
    regions = pd.DataFrame(regions).sort_values("taux_pondere_2025_2026", ascending=False)
    total = {"region": "Burkina Faso", "provinces": len(provinces),
             "eleves_primaire_2024_2025": int(provinces["eleves_primaire_2024_2025"].sum())}
    for a in annees:
        poids = provinces["eleves_primaire_2024_2025"].fillna(0)
        total[f"taux_pondere_{a}"] = round(float(np.average(provinces[f"taux_{a}"], weights=poids)), 2)
        total[f"abandons_estimes_{a}"] = int(provinces[f"abandons_estimes_{a}"].sum())
        total[f"provinces_risque_eleve_{a}"] = int((provinces[f"classe_{a}"] == "élevé").sum())
    total["alertes_rupture"] = int((provinces["risque_de_rupture"] == "élevé").sum())
    regions = pd.concat([regions, pd.DataFrame([total])], ignore_index=True)
    return provinces, regions


def carte_alerte(chemin: Path) -> Path:
    _, rapport, _ = _api()
    figure = rapport._carte("ensemble")
    figure.suptitle("Risque de décrochage au primaire, prévision 2025-2026 (hachures : alerte de rupture)",
                    fontsize=9, x=0.02, ha="left")
    figure.savefig(chemin, dpi=220, bbox_inches="tight", facecolor="white")
    return chemin


def rapports(dossier: Path) -> dict[str, int]:
    """Rapport national, rapports régionaux et fiches provinciales (PDF)."""
    _, rapport, donnees = _api()
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "rapport_national.pdf").write_bytes(rapport.rapport_national("ensemble"))
    regions = dossier / "regions"
    provinces = dossier / "provinces"
    for d in (regions, provinces):
        d.mkdir(exist_ok=True)
    t = donnees.tableau_ensemble
    for nom in sorted(t["region_nom"].unique()):
        (regions / f"rapport_region_{nom}.pdf").write_bytes(rapport.rapport_region(nom, "ensemble"))
    for _, r in t.sort_values("province_nom").iterrows():
        (provinces / f"fiche_province_{r['province_nom']}.pdf").write_bytes(
            rapport.rapport_province(r["province_pcode"], "ensemble"))
    return {"regions": len(list(regions.glob("*.pdf"))), "provinces": len(list(provinces.glob("*.pdf")))}


def _zipper(source: Path, archive: Path, exclus: set[str] = frozenset()) -> Path:
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(source.rglob("*")):
            if f.is_file() and not (set(f.relative_to(source).parts) & exclus):
                z.write(f, f.relative_to(source.parent).as_posix())
    return archive


def executer() -> dict[str, object]:
    sortie = config.verifier_ecriture(SORTIE)
    sortie.mkdir(parents=True, exist_ok=True)
    provinces, regions = indicateurs_cles()
    for nom, table in [("indicateurs_cles_province", provinces), ("indicateurs_cles_region", regions)]:
        table.to_csv(sortie / f"{nom}.csv", sep=config.SEPARATEUR, encoding=config.ENCODAGE_SORTIE, index=False)
    carte_alerte(sortie / "carte_alerte_2025_2026.png")
    compte = rapports(sortie / "rapports")
    for nom in ("regions", "provinces"):
        _zipper(sortie / "rapports" / nom, sortie / "rapports" / f"rapports_{nom}.zip")
    shutil.copy2(APPLICATION / "web" / "public" / "guide_sentinelle.pdf", sortie / "guide_sentinelle.pdf")
    _zipper(APPLICATION, sortie / "application_sentinelle_source.zip", EXCLUS_APPLICATION)
    return {"provinces": len(provinces), "regions": len(regions) - 1, **compte}


__all__ = ["executer", "indicateurs_cles", "LIEN_EN_LIGNE"]
