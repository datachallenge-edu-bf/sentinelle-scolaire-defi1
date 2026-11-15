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
régionaux sont répartis selon les élèves de leurs provinces l'année considérée.

Reconstruction des indicateurs des unités touchées (le modèle s'entraîne sur ces unités) :

- provinces scindées (effectifs communaux lus par la Sentinelle dans les annuaires régionaux
  de l'INSD, table fait_insd_commune) : les rapports qui dépendent d'effectifs (élèves par maître, par
  salle, part des filles, du privé, taux bruts et nets, scolarisation au post-primaire) sont
  corrigés par le rapport des clés communales de l'INSD (élèves, filles, privé, enseignants,
  salles, élèves du post-primaire) à la population ; les écoles fermées sont réparties
  selon les écoles fermées des communes ; la cible n'est pas observée à cette échelle : elle
  est laissée vide (à estimer à l'étape 04) et la cible de la province d'origine est gardée
  à part pour le recalage ;
- régions de 2025 : TBA, TBS, achèvement, CEP (et leurs indices de parité), préscolaire et
  part des écoles privées sont recalculés à partir des numérateurs et dénominateurs des
  provinces ; le contexte régional des provinces prend ces valeurs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config
from .panel import SEUIL_RUPTURE, STRUCTURELLES, annee_scolaire, debut, lire

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


CIBLES = ["abandon_suivant", "abandon_brut_suivant", "abandon_precedent", "redoublement_precedent",
          "promotion_precedente"]
# Rapport corrigé par (clé du numérateur / clé du dénominateur) pour une province scindée.
CORRECTIONS = {
    "part_filles": ("filles", "eleves"), "eleves_par_maitre": ("eleves", "enseignants"),
    "eleves_par_salle": ("eleves", "salles"), "part_eleves_prive": ("prive", "eleves"),
    "tba_province": ("eleves", "population"), "tbs_province": ("eleves", "population"),
    "tns_province": ("eleves", "population"), "achevement_province": ("eleves", "population"),
    "tbs_post_primaire_province": ("eleves_post_primaire", "population"),
}


def _effectifs_communaux() -> pd.DataFrame:
    """Élèves (total, filles, privé), enseignants, salles, écoles fermées et élèves du post-primaire par commune."""
    insd = lire("fait_insd_commune")
    def serie(indicateurs, modalite):
        partie = insd[insd["indicateur"].isin(indicateurs) & (insd["modalite"] == modalite)]
        # Le premier tableau publié prime ; l'autre (par sexe ou par statut) complète ses manques.
        partie = partie.assign(rang=partie["indicateur"].map({k: i for i, k in enumerate(indicateurs)}))
        return partie.sort_values("rang").drop_duplicates(["commune_pcode", "annee_scolaire"]).set_index(
            ["commune_pcode", "annee_scolaire"])["valeur"]
    table = pd.DataFrame({
        "eleves": serie(["eleves_par_sexe", "eleves_par_statut"], "T"),
        "filles": serie(["eleves_par_sexe"], "F"),
        "prive": serie(["eleves_par_statut"], "prive"),
        "enseignants": serie(["enseignants_par_sexe", "enseignants_par_statut"], "T"),
        "salles": serie(["salles"], "T"),
        "ecoles_fermees": serie(["ecoles_fermees"], "T"),
        "eleves_post_primaire": serie(["eleves_post_primaire_par_statut", "eleves_post_primaire_par_sexe"], "T"),
    })
    table.index = table.index.set_names(["commune_code", "annee"])
    return table.reset_index()


def _parts_communales(communes: pd.DataFrame, codes: list[str]) -> dict:
    """{(province de 2025, clé) : {année : part dans la province d'origine}}, années à communes complètes."""
    donnees = _effectifs_communaux()
    parts = {}
    for code in codes:
        ancienne = communes.loc[communes["province_pcode"] == code, "province_ancienne_pcode"].iloc[0]
        membres = communes[communes["province_ancienne_pcode"] == ancienne][["commune_pcode", "province_pcode"]]
        d = donnees[donnees["commune_code"].isin(membres["commune_pcode"])]
        for cle in [c for c in donnees.columns if c not in ("commune_code", "annee")]:
            large = d.pivot_table(index="annee", columns="commune_code", values=cle).reindex(
                columns=membres["commune_pcode"]).dropna()
            large = large[large.sum(axis=1) > 0]
            dedans = membres.loc[membres["province_pcode"] == code, "commune_pcode"]
            parts[(code, cle)] = (large[dedans].sum(axis=1) / large.sum(axis=1)).to_dict()
    return parts


# Clé incomplète pour une province (élèves du Soum : 2 communes sur 9 dans l'annuaire du Sahel) : clé de repli.
REPLIS = {"eleves": ["enseignants", "salles"]}


def _part_annee(parts: dict, code: str, cle: str, annee: str, replis: set | None = None) -> float | None:
    for candidate in [cle] + REPLIS.get(cle, []):
        serie = parts.get((code, candidate), {})
        if serie:
            if candidate != cle and replis is not None:
                replis.add(f"clé {cle} remplacée par {candidate}")
            proche = min(serie, key=lambda a: abs(debut(a) - debut(annee)))
            return serie[proche]
    return None


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
    # Clés communales de l'INSD : effectifs et rapports propres à chaque province scindée.
    parts = _parts_communales(communes, codes)
    population = dict(zip(table["province_pcode"], table["part_population"]))
    notes = {}
    for i in table.index[scindee]:
        code, annee = table.at[i, "province_pcode"], table.at[i, "annee_scolaire"]
        origine = table.at[i, "part_population"]
        replis = set()
        for colonne, ecart in [("effectif", 0), ("effectif_precedent", -1), ("effectif_suivant", 1)]:
            part = _part_annee(parts, code, "eleves", annee_scolaire(debut(annee) + ecart), replis)
            if part is not None and pd.notna(table.at[i, colonne]):
                table.at[i, colonne] = table.at[i, colonne] / origine * part
        for colonne in ["ecoles_fermees_province", "eleves_touches_province"]:
            part = _part_annee(parts, code, "ecoles_fermees", annee)
            if part is not None and pd.notna(table.at[i, colonne]):
                table.at[i, colonne] = table.at[i, colonne] / origine * part
        for colonne, (numerateur, denominateur) in CORRECTIONS.items():
            p_num = _part_annee(parts, code, numerateur, annee, replis)
            p_den = population[code] if denominateur == "population" else _part_annee(parts, code, denominateur, annee,
                                                                                         replis)
            if colonne in table and p_num is not None and p_den and pd.notna(table.at[i, colonne]):
                table.at[i, colonne] = table.at[i, colonne] * p_num / p_den
        if replis:
            notes[i] = " ; " + ", ".join(sorted(replis))
    table.loc[scindee, "evolution_effectifs"] = table["effectif"] / table["effectif_precedent"] - 1
    table.loc[scindee, "evolution_effectifs_suivante"] = table["effectif_suivant"] / table["effectif"] - 1
    table.loc[scindee, "choc_effectifs"] = table.loc[scindee, "evolution_effectifs"].abs() > SEUIL_RUPTURE
    table["ecart_achevement_entree_6e"] = table["achevement_province"] - table["tba_6e_province"]
    # Cible : observée pour l'ancienne province seulement ; gardée à part, laissée vide pour les provinces scindées.
    for colonne in CIBLES:
        table[f"{colonne}_province_origine"] = table[colonne]
        table.loc[scindee, colonne] = np.nan
    table["cible_observee"] = ~scindee & table["abandon_suivant"].notna()
    table.loc[scindee, "statut_cible"] = "à estimer (province scindée en 2025)"
    # Rapports à recalculer après la répartition.
    table["deplaces_pour_100_eleves"] = 100 * table["deplaces"] / table["effectif"].where(table["effectif"] > 0)
    table["adolescents_non_formelle_pour_1000_eleves"] = (1000 * table["adolescents_non_formelle"]
                                                          / table["effectif"].where(table["effectif"] > 0))
    table["methode_passage"] = np.where(
        scindee, "province scindée : effectifs et rapports corrigés par clés communales INSD, déplacés et RGPH 2019 "
                 "recalculés sur les communes, autres taux hérités, cible à estimer", "identique (code et nom de 2025)")
    for i, note in notes.items():
        table.at[i, "methode_passage"] += note
    table = table.drop(columns="part_population")
    flottants = table.select_dtypes("float").columns
    table[flottants] = table[flottants].round(4)
    autres = [c for c in table.columns if c not in IDENTIFIANTS_PROVINCE]
    return table[IDENTIFIANTS_PROVINCE + autres].sort_values(["province_pcode", "annee_scolaire"]).reset_index(drop=True)


def taux_regions_2025() -> pd.DataFrame:
    """Taux régionaux de 2025 recalculés à partir des numérateurs et dénominateurs des anciennes provinces."""
    communes = lire("commune")
    region_de = communes.drop_duplicates("province_ancienne_pcode").set_index("province_ancienne_pcode")["region_pcode"]
    s = lire("fait_conditions_scolarisation")
    s = s[(s["sous_tableau"] == "ensemble") & s["section"].isin(["tba", "tbs", "achevement", "cep"])
          & s["entite_pcode"].isin(region_de.index)]
    s = s.assign(region_pcode=s["entite_pcode"].map(region_de))
    sommes = s.groupby(["region_pcode", "annee_scolaire", "section", "variable"])["valeur"].sum(min_count=1).unstack(
        ["section", "variable"])
    sortie = pd.DataFrame(index=sommes.index)
    for section, nom in [("tba", "tba"), ("tbs", "tbs"), ("achevement", "taux_achevement")]:
        for sexe, suffixe in [("t", ""), ("f", "_filles"), ("g", "_garcons")]:
            if (section, f"numerateur_{sexe}") in sommes:
                sortie[f"{nom}{suffixe}"] = 100 * sommes[(section, f"numerateur_{sexe}")] / sommes[(section, f"denominateur_{sexe}")]
    for sexe, suffixe in [("t", ""), ("f", "_filles"), ("g", "_garcons")]:
        if ("cep", f"admis_{sexe}") in sommes:
            sortie[f"reussite_cep{suffixe}"] = 100 * sommes[("cep", f"admis_{sexe}")] / sommes[("cep", f"presents_{sexe}")]
    sortie["ips_tba"] = sortie["tba_filles"] / sortie["tba_garcons"]
    sortie["ips_tbs"] = sortie["tbs_filles"] / sortie["tbs_garcons"]
    sortie["ips_tap"] = sortie["taux_achevement_filles"] / sortie["taux_achevement_garcons"]
    offre = lire("fait_offre_province")
    offre = offre[offre["entite_pcode"].isin(region_de.index)].assign(region_pcode=lambda t: t["entite_pcode"].map(region_de))
    ecoles = offre.pivot_table(index=["region_pcode", "annee_scolaire"], columns="statut", values="ecoles", aggfunc="sum")
    if "prive" in ecoles and "total" in ecoles:
        sortie["part_ecoles_privees"] = (ecoles["prive"] / ecoles["total"]).reindex(sortie.index)
    pre = lire("fait_prescolaire_province")
    pre = pre[pre["entite_pcode"].isin(region_de.index) & (pre["sexe"] == "T")]
    pre = pre.assign(region_pcode=pre["entite_pcode"].map(region_de)).groupby(["region_pcode", "annee_scolaire"])[
        ["enfants_prescolarises", "population_prescolarisable"]].sum(min_count=1)
    sortie = sortie.join((100 * pre["enfants_prescolarises"] / pre["population_prescolarisable"]).rename(
        "tbs_prescolaire"), how="outer")
    return sortie


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
    # Taux des régions scindées : recalculés depuis les provinces (numérateurs et dénominateurs).
    recalcul = taux_regions_2025()
    cles = pd.MultiIndex.from_frame(table[["region_pcode", "annee_scolaire"]])
    for colonne in recalcul.columns:
        if colonne in table:
            valeurs = pd.Series(recalcul[colonne].reindex(cles).to_numpy(), index=table.index)
            table.loc[scindee, colonne] = valeurs[scindee].combine_first(table.loc[scindee, colonne])
    table.loc[scindee, "methode_passage"] = ("région scindée : taux recalculés depuis les provinces, effectifs "
                                             "répartis selon les élèves des provinces de l'année")
    pays = region[region["region_ancienne_pcode"] == "BF"].assign(region_pcode="BF", region_nom="Burkina Faso",
                                                                  methode_passage="pays (inchangé)")
    table = pd.concat([table.drop(columns="part"), pays], ignore_index=True)
    debut = ["region_pcode", "region_nom", "region_ancienne_pcode", "region_ancienne_nom", "annee_scolaire",
             "methode_passage"]
    flottants = table.select_dtypes("float").columns
    table[flottants] = table[flottants].round(4)
    return table[debut + [c for c in table.columns if c not in debut]].sort_values(
        ["region_pcode", "annee_scolaire"]).reset_index(drop=True)


CONTEXTE = {"tba_region": "tba", "tbs_region": "tbs", "taux_achevement_region": "taux_achevement",
            "ips_tbs_region": "ips_tbs", "ips_tap_region": "ips_tap", "tbs_prescolaire_region": "tbs_prescolaire",
            "part_ecoles_privees_region": "part_ecoles_privees"}


def contexte_regional_2025(province_2025: pd.DataFrame, region_2025: pd.DataFrame) -> pd.DataFrame:
    """Contexte régional des provinces : valeurs des régions de 2025 (CEP de la session précédente)."""
    region = region_2025.set_index(["region_pcode", "annee_scolaire"])
    cles = pd.MultiIndex.from_frame(province_2025[["region_pcode", "annee_scolaire"]])
    for colonne, origine in CONTEXTE.items():
        if colonne in province_2025 and origine in region:
            province_2025[colonne] = pd.Series(region[origine].reindex(cles).to_numpy(), index=province_2025.index)
    precedent = pd.MultiIndex.from_arrays([province_2025["region_pcode"],
                                           province_2025["annee_scolaire"].map(lambda a: annee_scolaire(debut(a) - 1))])
    province_2025["reussite_cep_precedente_region"] = region["reussite_cep"].reindex(precedent).to_numpy()
    touchees = province_2025["region_ancienne_pcode"].map(
        province_2025.groupby("region_ancienne_pcode")["region_pcode"].nunique()) > 1
    identiques = touchees & province_2025["methode_passage"].str.startswith("identique")
    province_2025.loc[identiques, "methode_passage"] = "identique (code et nom de 2025) ; contexte régional de 2025"
    return province_2025


def ecarts_recalcul_regional(region: pd.DataFrame) -> pd.Series:
    """Écart médian (points) entre taux recalculés et taux publiés, sur les régions inchangées."""
    recalcul = taux_regions_2025()
    communes = lire("commune")
    inchangees = communes.groupby("region_ancienne_pcode")["region_pcode"].nunique()
    inchangees = communes[communes["region_ancienne_pcode"].isin(inchangees[inchangees == 1].index)][
        ["region_ancienne_pcode", "region_pcode"]].drop_duplicates()
    publie = region.merge(inchangees, on="region_ancienne_pcode").set_index(["region_pcode", "annee_scolaire"])
    commun = publie.index.intersection(recalcul.index)
    return pd.Series({c: float((recalcul.loc[commun, c] - publie.loc[commun, c]).abs().median())
                      for c in ["tba", "tbs", "taux_achevement", "reussite_cep"] if c in publie and c in recalcul})


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
    cible = province_2025["abandon_suivant_province_origine"].to_numpy()
    cible_identique = pd.Series((cible == repris.to_numpy()) | (pd.isna(cible) & repris.isna().to_numpy()))
    ecarts = ecarts_recalcul_regional(region)
    scindees = province_2025[~province_2025["methode_passage"].str.contains("identique")]
    differencies = scindees.groupby(["province_ancienne_pcode", "annee_scolaire"])["tbs_province"].nunique()
    resultats = [
        ("decoupage_2025_recalcul_regional_valide", bool((ecarts <= 1.0).all()),
         "taux recalculés depuis les provinces contre taux publiés des 10 régions inchangées, écart médian (points) : "
         + ", ".join(f"{k} {v:.2f}" for k, v in ecarts.items())),
        ("decoupage_2025_provinces_scindees_differenciees", bool((differencies == 2).mean() >= 0.8),
         f"TBS distincts entre les deux moitiés pour {int((differencies == 2).sum())} couples "
         f"province × année sur {len(differencies)} (clés communales INSD)"),
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
        ("decoupage_2025_cible_origine_conservee", bool(cible_identique.all()),
         f"cible de la province d'origine conservée pour le recalage : {int(cible_identique.sum())} lignes sur "
         f"{len(cible_identique)} ; cible observée (entraînement) pour "
         f"{int(province_2025['cible_observee'].sum())} lignes"),
    ]
    return pd.DataFrame(resultats, columns=["controle", "conforme", "detail"])
