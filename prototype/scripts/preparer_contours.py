"""Regroupe les 45 provinces (Natural Earth, via le paquet npm datamaps) en 13 régions,
découpage encore utilisé par l'annuaire statistique 2024-2025."""
from pathlib import Path
import geopandas as gpd

DATA = Path(__file__).resolve().parents[1] / "data"
REGIONS = {
    "Boucle du Mouhoun": ["Balé", "Banwa", "Kossi", "Mou Houn", "Nayala", "Sourou"],
    "Cascades": ["Komoé", "Léraba"],
    "Centre": ["Kadiogo"],
    "Centre-Est": ["Boulgou", "Koulpélogo", "Kouritenga"],
    "Centre-Nord": ["Bam", "Namentenga", "Sanmatenga"],
    "Centre-Ouest": ["Boulkiemdé", "Sanguié", "Sissili", "Ziro"],
    "Centre-Sud": ["Bazéga", "Nahouri", "Zoundwéogo"],
    "Est": ["Gnagna", "Gourma", "Komondjari", "Kompienga", "Tapoa"],
    "Hauts-Bassins": ["Houet", "Kénédougou", "Tuy"],
    "Nord": ["Loroum", "Passoré", "Yatenga", "Zondoma"],
    "Plateau-Central": ["Ganzourgou", "Kourwéogo", "Oubritenga"],
    "Sahel": ["Oudalan", "Séno", "Soum", "Yagha"],
    "Sud-Ouest": ["Bougouriba", "Ioba", "Noumbiel", "Poni"],
}
prov2reg = {p: r for r, ps in REGIONS.items() for p in ps}

prov = gpd.read_file(DATA / "bfa.topo.json").set_crs(4326)
prov["province"] = prov["name"].replace({"Mou Houn": "Mouhoun", "Komoé": "Comoé"})
prov["region"] = prov["name"].map(prov2reg)
assert prov["region"].notna().all(), prov.loc[prov["region"].isna(), "name"].tolist()
prov[["province", "region", "geometry"]].to_file(DATA / "provinces_bfa_45.geojson", driver="GeoJSON")
reg = prov.dissolve(by="region", as_index=False)[["region", "geometry"]]
reg.to_file(DATA / "regions_bfa_13.geojson", driver="GeoJSON")
print(len(prov), "provinces ->", len(reg), "régions")
