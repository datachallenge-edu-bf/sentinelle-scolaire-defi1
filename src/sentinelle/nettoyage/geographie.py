"""Référentiel géographique et couches cartographiques.

La commune est le pivot entre les deux découpages : chaque commune COD-AB porte
son P-code actuel (17 régions, 47 provinces) et son ancien P-code (13 régions,
45 provinces), dont les quatre et six premiers caractères désignent l'ancienne
région et l'ancienne province. Les couches de chaque niveau sont obtenues en
regroupant les contours des communes, ce qui garantit des limites communes
identiques d'un niveau à l'autre.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

from .. import config
from .outils import lire_extrait, normaliser_nom

NIVEAUX = {
    "commune": "commune_pcode",
    "province": "province_pcode",
    "region": "region_pcode",
    "province_ancienne": "province_ancienne_pcode",
    "region_ancienne": "region_ancienne_pcode",
}

# Noms rencontrés dans les publications DGESS qui diffèrent de ceux d'OpenStreetMap.
ALIAS_ANCIENS = {
    "KOMONDJARI": "BF5203",
    "KOMANDJOARI": "BF5203",
    "KOMONDJOARI": "BF5203",
    "LESBALE": "BF4601",
    "LESBALES": "BF4601",
    "BALES": "BF4601",
    "CASCADE": "BF47",
    "HAUTBASSINS": "BF53",
    "PLATEAUCENTRAL": "BF55",
    "CENTREEST": "BF48",
    "CENTRENORD": "BF49",
    "CENTREOUEST": "BF50",
    "CENTRESUD": "BF51",
    "SUDOUEST": "BF57",
}
CODE_NATIONAL = "BF"
NOMS_NATIONAL = {"NATIONAL", "BURKINAFASO", "BURKINA", "TOTAL", "ENSEMBLE", "TOTALNATIONAL"}


def lire_communes() -> gpd.GeoDataFrame:
    """Contours officiels des 351 communes (COD-AB, version d'août 2025)."""
    chemin = f"/vsizip/{config.CONTOURS_CODAB.as_posix()}/bfa_admin3.geojson"
    return gpd.read_file(chemin, engine="pyogrio")


def noms_anciens() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Noms des 45 anciennes provinces et des 13 anciennes régions.

    COD-AB ne conserve que les anciens codes ; les noms correspondants sont repris
    du fichier des écoles OpenStreetMap, qui suit l'ancien découpage avec P-codes.
    """
    osm = lire_extrait("ecoles_osm")
    osm = osm[(osm["adm2_pcode"] != "") & (osm["adm1_pcode"] != "")]
    provinces = (osm[["adm2_pcode", "adm2_name"]].drop_duplicates("adm2_pcode")
                 .rename(columns={"adm2_pcode": "province_ancienne_pcode", "adm2_name": "province_ancienne_nom"}))
    regions = (osm[["adm1_pcode", "adm1_name"]].drop_duplicates("adm1_pcode")
               .rename(columns={"adm1_pcode": "region_ancienne_pcode", "adm1_name": "region_ancienne_nom"}))
    return provinces, regions


def referentiel_communes(communes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Table des communes avec leurs rattachements dans les deux découpages."""
    provinces_anc, regions_anc = noms_anciens()
    # Les centres fournis par COD-AB sont vides : ils sont calculés en projection métrique.
    centres = communes.geometry.to_crs(config.CRS_METRIQUE).centroid.to_crs(config.CRS_STOCKAGE)
    ref = gpd.GeoDataFrame({
        "commune_pcode": communes["adm3_pcode"],
        "commune_nom": communes["adm3_name"],
        "province_pcode": communes["adm2_pcode"],
        "province_nom": communes["adm2_name"],
        "region_pcode": communes["adm1_pcode"],
        "region_nom": communes["adm1_name"],
        "commune_ancienne_pcode": communes["adm3_pcode_old"],
        "province_ancienne_pcode": communes["adm3_pcode_old"].str[:6],
        "region_ancienne_pcode": communes["adm3_pcode_old"].str[:4],
        "superficie_km2": pd.to_numeric(communes["area_sqkm"], errors="coerce"),
        "latitude": centres.y.round(5),
        "longitude": centres.x.round(5),
    }, geometry=communes.geometry, crs=communes.crs)
    ref = ref.merge(provinces_anc, on="province_ancienne_pcode", how="left")
    ref = ref.merge(regions_anc, on="region_ancienne_pcode", how="left")
    colonnes = ["commune_pcode", "commune_nom", "province_pcode", "province_nom", "region_pcode", "region_nom",
                "commune_ancienne_pcode", "province_ancienne_pcode", "province_ancienne_nom",
                "region_ancienne_pcode", "region_ancienne_nom", "superficie_km2", "latitude", "longitude", "geometry"]
    return gpd.GeoDataFrame(ref[colonnes], geometry="geometry", crs=communes.crs).sort_values("commune_pcode")


def _regrouper(communes: gpd.GeoDataFrame, code: str, attributs: list[str]) -> gpd.GeoDataFrame:
    couche = communes[[code, *attributs, "superficie_km2", "geometry"]].dissolve(
        by=code, aggfunc={**{a: "first" for a in attributs}, "superficie_km2": "sum"})
    nb = communes.groupby(code).size().rename("nb_communes")
    return couche.join(nb).reset_index()


def couches(ref_communes: gpd.GeoDataFrame) -> dict[str, gpd.GeoDataFrame]:
    """Couches des cinq niveaux, toutes issues du regroupement des communes."""
    resultat = {"commune": ref_communes.reset_index(drop=True)}

    provinces = _regrouper(ref_communes, "province_pcode",
                           ["province_nom", "region_pcode", "region_nom", "province_ancienne_pcode",
                            "province_ancienne_nom"])
    partage = ref_communes.groupby("province_ancienne_pcode")["province_pcode"].nunique()
    provinces["province_ancienne_partagee"] = provinces["province_ancienne_pcode"].map(partage).gt(1)
    resultat["province"] = provinces

    resultat["region"] = _regrouper(ref_communes, "region_pcode", ["region_nom"])

    anciennes = _regrouper(ref_communes, "province_ancienne_pcode",
                           ["province_ancienne_nom", "region_ancienne_pcode", "region_ancienne_nom"])
    nouvelles = (ref_communes.groupby("province_ancienne_pcode")
                 .apply(lambda g: ", ".join(sorted(set(g["province_pcode"]))), include_groups=False)
                 .rename("provinces_actuelles"))
    resultat["province_ancienne"] = anciennes.merge(nouvelles, on="province_ancienne_pcode")

    resultat["region_ancienne"] = _regrouper(ref_communes, "region_ancienne_pcode", ["region_ancienne_nom"])
    return resultat


def table_alias(ref_communes: pd.DataFrame) -> pd.DataFrame:
    """Correspondance entre les noms rencontrés et les codes de l'ancien découpage.

    Les publications DGESS suivent l'ancien découpage : seuls les noms des anciennes
    provinces et régions y sont reconnus, pour éviter toute confusion avec les noms
    du nouveau découpage (par exemple Soum, ancienne province devenue région).
    """
    lignes = []
    for code, nom in ref_communes[["province_ancienne_pcode", "province_ancienne_nom"]].drop_duplicates().values:
        lignes.append((normaliser_nom(nom), code, "province_ancienne", nom, "OpenStreetMap"))
    for code, nom in ref_communes[["region_ancienne_pcode", "region_ancienne_nom"]].drop_duplicates().values:
        lignes.append((normaliser_nom(nom), code, "region_ancienne", nom, "OpenStreetMap"))
    for alias, code in ALIAS_ANCIENS.items():
        niveau = "region_ancienne" if len(code) == 4 else "province_ancienne"
        lignes.append((alias, code, niveau, alias, "variante relevée dans les publications DGESS"))
    for alias in NOMS_NATIONAL:
        lignes.append((alias, CODE_NATIONAL, "pays", alias, "libellé du total national"))
    alias = pd.DataFrame(lignes, columns=["nom_normalise", "pcode", "niveau", "nom_reference", "origine"])
    return alias.drop_duplicates("nom_normalise").sort_values(["niveau", "pcode"]).reset_index(drop=True)


def controle_couverture(couche: gpd.GeoDataFrame) -> dict:
    """Vérifie que la couche forme une mosaïque sans trou ni chevauchement."""
    return {
        "nb_entites": len(couche),
        "geometries_valides": bool(couche.is_valid.all()),
        "mosaique_valide": bool(shapely.coverage_is_valid(couche.geometry.values)),
    }


def simplifier_pour_le_web(couche: gpd.GeoDataFrame, tolerance: float = 0.01) -> gpd.GeoDataFrame:
    """Simplification qui préserve la mosaïque : les limites partagées restent identiques, sans trou."""
    simple = couche.copy()
    simple["geometry"] = shapely.coverage_simplify(couche.geometry.values, tolerance)
    return simple


def ecrire_contours_web(couches_niveaux: dict[str, gpd.GeoDataFrame], dossier: Path,
                        tolerance: float = 0.01, decimales: int = 4) -> pd.DataFrame:
    """Écrit des GeoJSON légers pour le prototype web et renvoie leurs caractéristiques."""
    dossier = config.verifier_ecriture(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    bilan = []
    for niveau, couche in couches_niveaux.items():
        simple = simplifier_pour_le_web(couche, tolerance)
        attributs = [c for c in simple.columns if c.endswith(("_pcode", "_nom")) or c == "province_ancienne_partagee"]
        chemin = dossier / f"{niveau}.geojson"
        chemin.unlink(missing_ok=True)
        simple[attributs + ["geometry"]].to_file(
            chemin, driver="GeoJSON", engine="pyogrio",
            layer_options={"COORDINATE_PRECISION": decimales, "RFC7946": "YES"},
        )
        # Le contrôle porte sur le fichier relu, après arrondi des coordonnées.
        relu = gpd.read_file(chemin, engine="pyogrio")
        bilan.append({
            "niveau": niveau,
            "fichier": chemin.name,
            "taille_ko": round(chemin.stat().st_size / 1024, 1),
            "points": int(shapely.get_num_coordinates(relu.geometry.values).sum()),
            **controle_couverture(relu),
        })
    return pd.DataFrame(bilan)
