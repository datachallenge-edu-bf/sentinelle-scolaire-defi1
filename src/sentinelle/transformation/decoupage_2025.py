"""Panels du modèle dans le découpage administratif de juillet 2025 (17 régions, 47 provinces).

Le modèle s'entraîne sur les 45 anciennes provinces, unités de publication des données
jusqu'en 2024-2025. Pour la restitution (carte du risque, alertes, recommandations), les
panels sont transposés dans les unités de 2025, avec les noms et codes du COD-AB.

Aucune province de 2025 ne réunit deux anciennes provinces : chacune reprend la ligne de
sa province d'origine. 43 sont identiques ; le Soum (Djelgodji, Karo-Peli) et la Tapoa
(Gobnangou, Dyamongou) sont scindés. Pour ces quatre provinces :

- les effectifs provinciaux (élèves, écoles fermées, apprenants…) sont répartis selon la
  part de la population de 2019 ;
- les déplacés sont recomptés sur leurs communes, à la même date de situation ;
- les variables du RGPH 2019 sont recalculées sur leurs communes (moyenne pondérée par la
  population) ; consommation et inégalités, publiées par province seulement, sont héritées ;
- les taux (dont la cible) et les contextes régionaux sont hérités de l'ancienne province.

Les régions de 2025 réunissent des provinces anciennes entières. Dix sont d'anciennes
régions renommées ; la Boucle du Mouhoun, l'Est et le Sahel sont scindés : leurs effectifs
régionaux sont répartis selon les élèves de leurs provinces l'année considérée, leurs taux
sont hérités.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .panel import STRUCTURELLES, annee_scolaire, lire

EFFECTIFS_PROVINCE = ["effectif", "effectif_precedent", "effectif_suivant", "deplaces", "ecoles_fermees_province",
                      "eleves_touches_province", "adolescents_non_formelle", "centres_non_formelle_adolescents",
                      "grande_section_province"]
EFFECTIFS_REGION = ["effectif_primaire", "effectif_primaire_filles", "nouveaux_inscrits_cp1",
                    "nouveaux_inscrits_cp1_filles", "ecoles_primaires", "ecoles_primaires_publiques",
                    "ecoles_primaires_privees", "effectif_prescolaire", "structures_prescolaire",
                    "structures_prescolaire_publiques", "salles_prescolaire"]
IDENTIFIANTS_PROVINCE = ["province_pcode", "province_nom", "region_pcode", "region_nom", "province_ancienne_pcode",
                         "province_ancienne_nom", "region_ancienne_pcode", "region_ancienne_nom", "annee_scolaire",
                         "methode_passage"]


def _communes() -> pd.DataFrame:
    communes = lire("commune")
    vie = lire("fait_conditions_vie")
    population = vie[vie["niveau_geo"] == "commune"].set_index("entite_pcode")["population"]
    return communes.assign(population=communes["commune_pcode"].map(population))


def correspondance_provinces(communes: pd.DataFrame) -> pd.DataFrame:
    """Province de 2025, province d'origine, part de la population de 2019 et noms."""
    table = communes.groupby(["province_pcode", "province_nom", "region_pcode", "region_nom",
                              "province_ancienne_pcode"], as_index=False)["population"].sum()
    table["part_population"] = table["population"] / table.groupby("province_ancienne_pcode")["population"].transform("sum")
    return table.drop(columns="population")


def _rgph_par_province(communes: pd.DataFrame, codes: list[str]) -> pd.DataFrame:
    vie = lire("fait_conditions_vie")
    vie = vie[vie["niveau_geo"] == "commune"].merge(communes[["commune_pcode", "province_pcode"]],
                                                    left_on="entite_pcode", right_on="commune_pcode")
    vie = vie[vie["province_pcode"].isin(codes)]
    lignes = []
    for code, groupe in vie.groupby("province_pcode"):
        ligne = {"province_pcode": code}
        for source, cible in STRUCTURELLES.items():
            valide = groupe[source].notna()
            poids = groupe.loc[valide, "population"]
            ligne[cible] = float((groupe.loc[valide, source] * poids).sum() / poids.sum()) if valide.any() else np.nan
        lignes.append(ligne)
    return pd.DataFrame(lignes).set_index("province_pcode")


def _deplaces_par_province_2025(communes: pd.DataFrame, codes: list[str]) -> pd.DataFrame:
    """Déplacés des provinces de 2025 indiquées : dernière situation des six mois avant le 31 décembre."""
    pdi = lire("fait_pdi_commune").merge(communes[["commune_pcode", "province_pcode"]], on="commune_pcode")
    pdi = pdi[pdi["province_pcode"].isin(codes)]
    pdi = pdi.groupby(["province_pcode", "date_situation"], as_index=False)["pdi_total"].sum()
    pdi["date"] = pd.to_datetime(pdi["date_situation"])
    lignes = []
    for annee in range(2015, 2025):
        borne = pd.Timestamp(f"{annee}-12-31")
        fenetre = pdi[(pdi["date"] <= borne) & (pdi["date"] > borne - pd.DateOffset(months=6))]
        if not fenetre.empty:
            derniere = fenetre[fenetre["date"] == fenetre["date"].max()]
            lignes.append(derniere.assign(annee_scolaire=annee_scolaire(annee)))
    if not lignes:
        return pd.DataFrame(columns=["province_pcode", "annee_scolaire", "deplaces"])
    return pd.concat(lignes)[["province_pcode", "annee_scolaire", "pdi_total"]].rename(columns={"pdi_total": "deplaces"})


def panel_province_2025(panel: pd.DataFrame) -> pd.DataFrame:
    communes = _communes()
    passage = correspondance_provinces(communes)
    table = passage.merge(panel.drop(columns=["provinces_actuelles"]), on="province_ancienne_pcode", how="left")
    scindee = table["part_population"] < 0.999
    effectifs = [c for c in EFFECTIFS_PROVINCE if c in table]
    table.loc[scindee, effectifs] = table.loc[scindee, effectifs].multiply(table.loc[scindee, "part_population"], axis=0)
    codes = sorted(table.loc[scindee, "province_pcode"].unique())
    # Déplacés recomptés sur les communes ; RGPH 2019 recalculé sur les communes.
    deplaces = _deplaces_par_province_2025(communes, codes).set_index(["province_pcode", "annee_scolaire"])["deplaces"]
    cles = list(zip(table["province_pcode"], table["annee_scolaire"]))
    recomptes = pd.Series([deplaces.get(k, np.nan) for k in cles], index=table.index)
    table.loc[scindee, "deplaces"] = recomptes[scindee].combine_first(table.loc[scindee, "deplaces"])
    rgph = _rgph_par_province(communes, codes)
    for colonne in rgph.columns:
        table.loc[scindee, colonne] = table.loc[scindee, "province_pcode"].map(rgph[colonne])
    # Rapports à recalculer après la répartition.
    table["deplaces_pour_100_eleves"] = 100 * table["deplaces"] / table["effectif"].where(table["effectif"] > 0)
    table["adolescents_non_formelle_pour_1000_eleves"] = (1000 * table["adolescents_non_formelle"]
                                                          / table["effectif"].where(table["effectif"] > 0))
    table["methode_passage"] = np.where(
        scindee, "province scindée : effectifs répartis selon la population 2019, déplacés et RGPH 2019 recalculés "
                 "sur les communes, taux et cible hérités de l'ancienne province", "identique (code et nom de 2025)")
    table = table.drop(columns="part_population")
    flottants = table.select_dtypes("float").columns
    table[flottants] = table[flottants].round(4)
    autres = [c for c in table.columns if c not in IDENTIFIANTS_PROVINCE]
    return table[IDENTIFIANTS_PROVINCE + autres].sort_values(["province_pcode", "annee_scolaire"]).reset_index(drop=True)


def panel_region_2025(region: pd.DataFrame, province_2025: pd.DataFrame) -> pd.DataFrame:
    """Régions de 2025 et pays : régions renommées reprises, régions scindées réparties selon leurs élèves."""
    passage = province_2025[["region_pcode", "region_nom", "region_ancienne_pcode"]].drop_duplicates()
    eleves = province_2025.groupby(["region_ancienne_pcode", "region_pcode", "annee_scolaire"])["effectif"].sum(
        min_count=1).rename("eleves").reset_index()
    eleves["part"] = eleves["eleves"] / eleves.groupby(["region_ancienne_pcode", "annee_scolaire"])["eleves"].transform("sum")
    table = passage.merge(region, on="region_ancienne_pcode", how="left").merge(
        eleves[["region_pcode", "annee_scolaire", "part"]], on=["region_pcode", "annee_scolaire"], how="left")
    # Années sans panel provincial (avant 2016-2017) : part de la population de 2019.
    communes = _communes()
    population = communes.groupby(["region_ancienne_pcode", "region_pcode"])["population"].sum()
    part_population = population / population.groupby(level="region_ancienne_pcode").transform("sum")
    table["part"] = table["part"].fillna(pd.Series(
        [part_population.get((a, n), np.nan) for a, n in zip(table["region_ancienne_pcode"], table["region_pcode"])],
        index=table.index))
    nb = passage.groupby("region_ancienne_pcode")["region_pcode"].nunique()
    scindee = table["region_ancienne_pcode"].map(nb) > 1
    effectifs = [c for c in EFFECTIFS_REGION if c in table]
    table.loc[scindee, effectifs] = table.loc[scindee, effectifs].multiply(table.loc[scindee, "part"], axis=0)
    table["methode_passage"] = np.where(scindee, "région scindée : effectifs répartis selon les élèves des provinces "
                                                 "de l'année (à défaut, la population 2019), taux hérités",
                                        "identique (région renommée en 2025)")
    pays = region[region["region_ancienne_pcode"] == "BF"].assign(region_pcode="BF", region_nom="Burkina Faso",
                                                                  methode_passage="pays (inchangé)")
    table = pd.concat([table.drop(columns="part"), pays], ignore_index=True)
    debut = ["region_pcode", "region_nom", "region_ancienne_pcode", "region_ancienne_nom", "annee_scolaire",
             "methode_passage"]
    flottants = table.select_dtypes("float").columns
    table[flottants] = table[flottants].round(4)
    return table[debut + [c for c in table.columns if c not in debut]].sort_values(
        ["region_pcode", "annee_scolaire"]).reset_index(drop=True)


def controles(panel: pd.DataFrame, province_2025: pd.DataFrame, region: pd.DataFrame,
              region_2025: pd.DataFrame) -> pd.DataFrame:
    annees = panel["annee_scolaire"].nunique()
    somme = lambda t, c: t.groupby("annee_scolaire")[c].sum()
    ecart_effectif = (somme(province_2025, "effectif") - somme(panel, "effectif")).abs().max()
    ecart_deplaces = (somme(province_2025, "deplaces") - somme(panel, "deplaces")).abs().max()
    nouvelles = region_2025[region_2025["region_pcode"] != "BF"]
    ecart_region = (somme(nouvelles, "effectif_primaire")
                    - somme(region[region["region_ancienne_pcode"] != "BF"], "effectif_primaire")).abs().max()
    origine = panel.set_index(["province_ancienne_pcode", "annee_scolaire"])["abandon_suivant"]
    repris = origine.reindex(pd.MultiIndex.from_frame(province_2025[["province_ancienne_pcode", "annee_scolaire"]]))
    cible = province_2025["abandon_suivant"].to_numpy()
    cible_identique = pd.Series((cible == repris.to_numpy()) | (pd.isna(cible) & repris.isna().to_numpy()))
    resultats = [
        ("decoupage_2025_47_provinces", province_2025["province_pcode"].nunique() == 47
         and len(province_2025) == 47 * annees and province_2025["province_nom"].notna().all(),
         f"{province_2025['province_pcode'].nunique()} provinces de 2025 × {annees} années, noms du COD-AB"),
        ("decoupage_2025_17_regions", nouvelles["region_pcode"].nunique() == 17 and nouvelles["region_nom"].notna().all(),
         f"{nouvelles['region_pcode'].nunique()} régions de 2025 et le pays"),
        ("decoupage_2025_effectifs_conserves", bool(ecart_effectif <= 1) and bool(ecart_region <= 1),
         f"élèves : somme des 47 provinces = somme des 45 anciennes (écart maximal {ecart_effectif:.2f}) ; "
         f"somme des 17 régions = somme des 13 (écart {ecart_region:.2f})"),
        ("decoupage_2025_deplaces_conserves", bool(ecart_deplaces <= 1),
         f"déplacés recomptés sur les communes : total national inchangé (écart maximal {ecart_deplaces:.0f})"),
        ("decoupage_2025_cible_heritee", bool(cible_identique.all()),
         f"cible (abandon de t à t+1) des 47 provinces égale à celle de leur province d'origine : "
         f"{int(cible_identique.sum())} lignes sur {len(cible_identique)}"),
    ]
    return pd.DataFrame(resultats, columns=["controle", "conforme", "detail"])
