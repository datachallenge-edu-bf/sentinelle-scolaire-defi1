"""Contrôles automatiques des tables nettoyées.

1. Complétude : chaque édition couvre les 45 anciennes provinces.
2. Cohérence interne : garçons + filles = total.
3. Sommes : la somme des provinces retrouve le total de chaque ancienne région
   publié dans le même tableau, et le total régional et national de la base
   principale DGESS remise par les organisateurs.
4. Jointure cartographique : chaque province du panel trouve son contour.
"""

from __future__ import annotations

import pandas as pd

from .outils import lire_extrait, normaliser_nom

TOLERANCE_RELATIVE = 0.005


def effectifs_base_principale(alias: pd.DataFrame) -> pd.DataFrame:
    """Effectifs du primaire par ancienne région, sexe et année (feuille 1 de la base principale)."""
    brut = lire_extrait("dgess_base_principale")
    feuille = brut[brut["feuille"] == "Feuil1"]
    entete = feuille[feuille["col1"].str.upper() == "REGION"].iloc[0]
    colonnes_annees = {c: entete[c].split("\n")[0].strip() for c in feuille.columns
                       if c.startswith("col") and entete[c][:4].isdigit()}
    codes = {r.nom_normalise: r.pcode for r in alias.itertuples()}
    sexes = {"GARCONS": "G", "FILLES": "F", "TOTAL": "T"}

    lignes, region = [], None
    for _, row in feuille.iterrows():
        if row["col1"].strip():
            region = codes.get(normaliser_nom(row["col1"]))
        sexe = sexes.get(normaliser_nom(row["col2"]))
        if region is None or sexe is None:
            continue
        for colonne, annee in colonnes_annees.items():
            if row[colonne].strip():
                lignes.append({"entite_pcode": region, "sexe": sexe, "annee_scolaire": annee,
                               "effectif_publie": float(row[colonne])})
    return pd.DataFrame(lignes)


def completude(table: pd.DataFrame, cle_annee: str, attendu: int = 45) -> pd.DataFrame:
    provinces = table[table["niveau_geo"] == "province_ancienne"]
    n = provinces.groupby(cle_annee)["entite_pcode"].nunique().rename("provinces").reset_index()
    n["attendu"] = attendu
    n["conforme"] = n["provinces"] == attendu
    return n


def coherence_sexes(effectifs: pd.DataFrame) -> pd.DataFrame:
    """Lignes où garçons + filles diffère du total."""
    cle = ["annee_publication", "annee_scolaire", "entite_pcode", "niveau"]
    large = effectifs.pivot_table(index=cle, columns="sexe", values="effectif", aggfunc="first")
    large["ecart"] = large["G"] + large["F"] - large["T"]
    return large[large["ecart"].abs() > 0].reset_index()


RATIO_FILLES_GARCONS = (0.8, 1.25)


def repartition_sexes(effectifs: pd.DataFrame) -> pd.DataFrame:
    """Entités et années où le rapport filles / garçons de l'effectif total est invraisemblable.

    L'annuaire 2024-2025 donne pour plusieurs provinces un total juste mais une
    répartition entre garçons et filles impossible (par exemple 33 313 garçons et
    84 353 filles au CP1 du Kadiogo). Pour ces cas, seul le total est utilisable.
    """
    cle = ["annee_publication", "annee_scolaire", "entite_pcode", "niveau_geo"]
    total = effectifs[effectifs["niveau"] == "Total"]
    large = total.pivot_table(index=cle, columns="sexe", values="effectif", aggfunc="first").reset_index()
    large["ratio_filles_garcons"] = (large["F"] / large["G"]).round(3)
    bas, haut = RATIO_FILLES_GARCONS
    return large[(large["ratio_filles_garcons"] < bas) | (large["ratio_filles_garcons"] > haut)]


def sommes_provinces_regions(effectifs: pd.DataFrame, communes: pd.DataFrame,
                             base_principale: pd.DataFrame) -> pd.DataFrame:
    """Somme des provinces comparée aux totaux régionaux publiés (annuaire et base principale)."""
    region_de = communes.drop_duplicates("province_ancienne_pcode").set_index(
        "province_ancienne_pcode")["region_ancienne_pcode"]
    total = effectifs[effectifs["niveau"] == "Total"]
    provinces = total[total["niveau_geo"] == "province_ancienne"].copy()
    provinces["region"] = provinces["entite_pcode"].map(region_de)

    cle = ["annee_publication", "annee_scolaire", "region", "sexe"]
    somme = provinces.groupby(cle)["effectif"].sum().rename("somme_provinces").reset_index()
    regions = total[total["niveau_geo"] == "region_ancienne"].rename(
        columns={"entite_pcode": "region", "effectif": "total_annuaire"})[cle + ["total_annuaire"]]
    bp = base_principale.rename(columns={"entite_pcode": "region", "effectif_publie": "total_base_principale"})

    res = somme.merge(regions, on=cle, how="left").merge(bp, on=["region", "sexe", "annee_scolaire"], how="left")
    res["ecart_annuaire"] = (res["somme_provinces"] / res["total_annuaire"] - 1).round(4)
    res["ecart_base_principale"] = (res["somme_provinces"] / res["total_base_principale"] - 1).round(4)
    return res


def sommes_nationales(effectifs: pd.DataFrame, base_principale: pd.DataFrame) -> pd.DataFrame:
    """Somme des 45 provinces comparée au total national de la base principale."""
    total = effectifs[(effectifs["niveau"] == "Total") & (effectifs["niveau_geo"] == "province_ancienne")]
    somme = total.groupby(["annee_publication", "annee_scolaire", "sexe"])["effectif"].sum().rename(
        "somme_provinces").reset_index()
    national = base_principale[base_principale["entite_pcode"] == "BF"].rename(
        columns={"effectif_publie": "total_national_publie"})[["annee_scolaire", "sexe", "total_national_publie"]]
    res = somme.merge(national, on=["annee_scolaire", "sexe"], how="inner")
    res["ecart"] = (res["somme_provinces"] / res["total_national_publie"] - 1).round(4)
    return res


def jointure_contours(table: pd.DataFrame, cle_annee: str, contours: pd.DataFrame) -> pd.DataFrame:
    """Pour chaque année, nombre de provinces du panel qui trouvent leur contour."""
    codes = set(contours["province_ancienne_pcode"])
    provinces = table[table["niveau_geo"] == "province_ancienne"]
    res = provinces.groupby(cle_annee)["entite_pcode"].agg(
        provinces="nunique",
        avec_contour=lambda s: len(set(s) & codes),
        sans_contour=lambda s: ", ".join(sorted(set(s) - codes)),
    ).reset_index()
    res["contours_sans_donnees"] = provinces.groupby(cle_annee)["entite_pcode"].agg(
        lambda s: ", ".join(sorted(codes - set(s)))).values
    return res


def synthese(controles: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Une ligne par contrôle : conforme ou non, avec le détail."""
    lignes = []

    for nom in ("completude_flux", "completude_effectifs"):
        t = controles[nom]
        lignes.append({"controle": nom, "conforme": bool(t["conforme"].all()),
                       "detail": f"{int(t['provinces'].min())} à {int(t['provinces'].max())} provinces par année"})

    t = controles["coherence_sexes"]
    lignes.append({"controle": "coherence_sexes", "conforme": t.empty,
                   "detail": f"{len(t)} lignes où garçons + filles diffère du total"})

    t = controles["repartition_sexes"]
    t = t[t["niveau_geo"] == "province_ancienne"]
    detail = ", ".join(f"{a} : {n}" for a, n in t.groupby("annee_scolaire").size().items()) or "aucune"
    lignes.append({"controle": "repartition_filles_garcons_plausible", "conforme": t.empty,
                   "detail": f"provinces hors [{RATIO_FILLES_GARCONS[0]} ; {RATIO_FILLES_GARCONS[1]}] par année : {detail}"})

    t = controles["sommes_regions"].dropna(subset=["ecart_annuaire"])
    hors = t[t["ecart_annuaire"].abs() > TOLERANCE_RELATIVE]
    lignes.append({"controle": "somme_provinces_egale_total_regional_annuaire", "conforme": hors.empty,
                   "detail": f"{len(hors)} écarts > {TOLERANCE_RELATIVE:.1%} sur {len(t)} comparaisons"})

    t = controles["sommes_regions"]
    t = t[t["annee_publication"] == "2024-2025"].dropna(subset=["ecart_base_principale"])
    hors = t[t["ecart_base_principale"].abs() > TOLERANCE_RELATIVE]
    lignes.append({"controle": "somme_provinces_egale_total_regional_base_principale", "conforme": hors.empty,
                   "detail": f"{len(hors)} écarts > {TOLERANCE_RELATIVE:.1%} sur {len(t)} comparaisons (édition 2024-2025)"})

    t = controles["sommes_nationales"]
    t = t[t["annee_publication"] == "2024-2025"]
    hors = t[t["ecart"].abs() > TOLERANCE_RELATIVE]
    lignes.append({"controle": "somme_provinces_egale_total_national_base_principale", "conforme": hors.empty,
                   "detail": f"{len(hors)} écarts > {TOLERANCE_RELATIVE:.1%} sur {len(t)} comparaisons (édition 2024-2025)"})

    for nom in ("jointure_contours_flux", "jointure_contours_effectifs"):
        t = controles[nom]
        lignes.append({"controle": nom, "conforme": bool((t["avec_contour"] == 45).all()),
                       "detail": f"{int(t['avec_contour'].min())} à {int(t['avec_contour'].max())} provinces sur 45 avec contour"})
    return pd.DataFrame(lignes)
