"""Étape 03 : table d'analyse du risque de décrochage.

Une ligne par ancienne province (45) et par année scolaire t. La ligne réunit :

- la cible : l'abandon apparent du cycle (CP1 à CM1) entre t et t+1, recalculé à
  partir des effectifs ; elle est vide pour la dernière année (à prévoir) et mise
  de côté quand les effectifs varient de plus de 30 % entre t et t+1 (rupture de
  scolarisation : fermetures ou réouvertures massives d'écoles) ;
- des variables connues à la date t uniquement, pour que le modèle ne voie jamais
  l'avenir : abandon et redoublement du passage précédent, évolution des
  effectifs, structure des effectifs, offre scolaire, déplacés internes, écoles
  fermées, et le contexte de la région tiré de la base principale DGESS (taux
  bruts d'admission et de scolarisation, taux d'achèvement, parité, préscolaire,
  réussite au CEP de la session précédente), l'éducation non formelle des
  adolescents (campagnes 2018 à 2020 et 2024) et le préscolaire (2023-2024 et
  2024-2025) de la province, et ses caractéristiques structurelles mesurées au
  recensement de 2019 (pauvreté, travail des enfants, enfants hors de l'école,
  mariage précoce, alphabétisation, actes de naissance, électricité, téléphone),
  constantes d'une année à l'autre ; enfin les conditions de scolarisation de
  l'année t (équipement des écoles, distance, taille des écoles, logements de
  maîtres, manuels, mobilier, profession des parents, état des salles, taux par
  province, réussite au CEP de la session précédente).

Deux tables complètent le panel : ``panel_region_annee`` reprend tous les
indicateurs régionaux de la base principale (13 régions et le pays), et
``serie_nationale_annee`` les ventilations publiées seulement au niveau national
(statut, milieu, classe, sections du préscolaire).

Les valeurs absentes des sources restent vides : aucune n'est inventée.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config
from ..indicateurs import flux_par_classe, taux

SEUIL_RUPTURE = 0.30
PREMIERE_ANNEE = "2016-2017"


def lire(nom: str) -> pd.DataFrame:
    return pd.read_csv(config.SORTIE_NETTOYAGE / f"{nom}.csv", sep=config.SEPARATEUR,
                       encoding=config.ENCODAGE_SORTIE, low_memory=False)


def debut(annee: str) -> int:
    return int(str(annee)[:4])


def annee_scolaire(debut_annee: int) -> str:
    return f"{debut_annee}-{debut_annee + 1}"


def _effectifs() -> pd.DataFrame:
    eff = lire("fait_effectifs_retenus")
    return eff[eff["niveau_geo"] == "province_ancienne"]


def _flux(effectifs: pd.DataFrame) -> pd.DataFrame:
    """Taux du cycle CP1 à CM1 pour chaque passage t vers t+1, filles et garçons réunis."""
    tous = effectifs[effectifs["sexe"] == "T"]
    cycle = taux(flux_par_classe(tous), ["entite_pcode", "annee_scolaire"])
    return cycle.rename(columns={"entite_pcode": "province_ancienne_pcode"})


def _structure(effectifs: pd.DataFrame) -> pd.DataFrame:
    """Effectif total, part des filles, poids du CP1 et du CM2, par province et année."""
    cles = ["entite_pcode", "annee_scolaire"]
    total = effectifs[effectifs["niveau"] == "Total"].pivot_table(index=cles, columns="sexe", values="effectif")
    fiable = effectifs.groupby(cles)["repartition_sexe_fiable"].first()
    classes = effectifs[effectifs["sexe"] == "T"].pivot_table(index=cles, columns="niveau", values="effectif")
    structure = pd.DataFrame({
        "effectif": total["T"],
        "part_filles": (total["F"] / total["T"]).where(fiable),
        "part_cp1": classes["CP1"] / classes["Total"],
        "rapport_cm2_cp1": classes["CM2"] / classes["CP1"],
    }).reset_index()
    return structure.rename(columns={"entite_pcode": "province_ancienne_pcode"})


def _offre() -> pd.DataFrame:
    offre = lire("fait_offre_province")
    offre = offre[offre["niveau_geo"] == "province_ancienne"]
    total = offre[offre["statut"] == "total"].set_index(["entite_pcode", "annee_scolaire"])
    prive = offre[offre["statut"] == "prive"].set_index(["entite_pcode", "annee_scolaire"])
    resultat = pd.DataFrame({
        "eleves_par_maitre": total["eleves_par_maitre"],
        "eleves_par_salle": total["eleves_par_salle"],
        "part_eleves_prive": prive["eleves"].reindex(total.index) / total["eleves"],
    }).reset_index()
    return resultat.rename(columns={"entite_pcode": "province_ancienne_pcode"})


def deplaces_par_province() -> pd.DataFrame:
    """Déplacés internes par ancienne province et date de situation (somme des communes)."""
    pdi = lire("fait_pdi_commune")
    communes = lire("commune")[["commune_pcode", "province_ancienne_pcode"]]
    pdi = pdi.merge(communes, on="commune_pcode", how="left")
    return (pdi.groupby(["province_ancienne_pcode", "date_situation"], as_index=False)
            .agg(deplaces=("pdi_total", "sum"), enfants_deplaces=("pdi_enfants", lambda v: v.sum(min_count=1))))


def _deplaces_a_la_rentree() -> pd.DataFrame:
    """Dernière situation connue au 31 décembre de l'année de rentrée, pour chaque province."""
    pdi = deplaces_par_province()
    pdi["date"] = pd.to_datetime(pdi["date_situation"])
    lignes = []
    for annee in range(2015, 2025):
        borne = pd.Timestamp(f"{annee}-12-31")
        avant = pdi[(pdi["date"] <= borne) & (pdi["date"] > borne - pd.DateOffset(months=6))]
        if avant.empty:
            continue
        derniere = avant[avant["date"] == avant["date"].max()]
        lignes.append(derniere.assign(annee_scolaire=annee_scolaire(annee)))
    if not lignes:
        return pd.DataFrame(columns=["province_ancienne_pcode", "annee_scolaire", "deplaces", "date_deplaces"])
    retenu = pd.concat(lignes)
    return retenu.rename(columns={"date_situation": "date_deplaces"})[
        ["province_ancienne_pcode", "annee_scolaire", "deplaces", "date_deplaces"]]


def _ecoles_fermees() -> pd.DataFrame:
    """Écoles fermées : moyenne des rapports de l'année scolaire (octobre à septembre).

    Niveau provincial : seulement les rapports jugés fiables. Niveau régional : phrases
    de synthèse des rapports (tous ordres d'enseignement), affectées aux provinces de la région.
    """
    def annee_de(mois: str) -> str:
        date = pd.Timestamp(str(mois)[:7] + "-01")
        return annee_scolaire(date.year if date.month >= 10 else date.year - 1)

    esu = lire("fait_esu_province")
    esu = esu[(esu["type"] == "fermes") & esu["rapport_fiable"]]
    esu = esu.assign(annee_scolaire=esu["mois"].map(annee_de))
    provinces = (esu.groupby(["province_ancienne_pcode", "annee_scolaire"], as_index=False)
                 .agg(ecoles_fermees_province=("etablissements", "mean"),
                      eleves_touches_province=("eleves_total", "mean")))

    region = lire("fait_esu_region")
    region = region.assign(annee_scolaire=region["mois"].map(annee_de))
    regions = (region.groupby(["region_ancienne_pcode", "annee_scolaire"], as_index=False)
               .agg(ecoles_fermees_region=("etablissements_fermes", "mean"),
                    eleves_affectes_region=("eleves_affectes", "mean")))
    return provinces, regions


# Base principale DGESS ------------------------------------------------------------------------------

# Nom de colonne -> (tableau, filtre) ; le filtre porte sur sexe, statut, milieu et classe.
_REGIONAL = {
    "effectif_primaire": ("Feuil1 T1", {"sexe": "T"}),
    "effectif_primaire_filles": ("Feuil1 T1", {"sexe": "F"}),
    "nouveaux_inscrits_cp1": ("Feuil5 T5", {"sexe": "T"}),
    "nouveaux_inscrits_cp1_filles": ("Feuil5 T5", {"sexe": "F"}),
    "tba": ("Feuil6 T6", {"sexe": "T"}),
    "tba_filles": ("Feuil6 T6", {"sexe": "F"}),
    "tba_garcons": ("Feuil6 T6", {"sexe": "G"}),
    "tbs": ("Feuil7 T7", {"sexe": "T"}),
    "tbs_filles": ("Feuil7 T7", {"sexe": "F"}),
    "tbs_garcons": ("Feuil7 T7", {"sexe": "G"}),
    "taux_achevement": ("Feuil8 T8", {"sexe": "T"}),
    "taux_achevement_filles": ("Feuil8 T8", {"sexe": "F"}),
    "taux_achevement_garcons": ("Feuil8 T8", {"sexe": "G"}),
    "reussite_cep": ("Feuil9 T9", {"sexe": "T"}),
    "reussite_cep_filles": ("Feuil9 T9", {"sexe": "F"}),
    "reussite_cep_garcons": ("Feuil9 T9", {"sexe": "G"}),
    "ips_tba": ("Feuil10 T10", {}),
    "ips_tbs": ("Feuil11 T11", {}),
    "ips_tap": ("Feuil12 T12", {}),
    "ecoles_primaires": ("Feuil13 T13", {"statut": "total"}),
    "ecoles_primaires_publiques": ("Feuil13 T13", {"statut": "public"}),
    "ecoles_primaires_privees": ("Feuil13 T13", {"statut": "prive"}),
    "effectif_prescolaire": ("PRESCOLAIRE T1", {"sexe": "T"}),
    "tbs_prescolaire": ("PRESCOLAIRE T5", {"sexe": "T"}),
    "ips_tbs_prescolaire": ("PRESCOLAIRE T6", {}),
    "structures_prescolaire": ("PRESCOLAIRE T7", {"statut": "total"}),
    "structures_prescolaire_publiques": ("PRESCOLAIRE T7", {"statut": "public"}),
    "salles_prescolaire": ("PRESCOLAIRE T8", {"statut": "total"}),
}

_CLASSES = ["CP1", "CP2", "CE1", "CE2", "CM1", "CM2"]
_NATIONAL = {
    "effectif_primaire_public": ("Feuil2 T2", {"statut": "public"}),
    "effectif_primaire_prive": ("Feuil2 T2", {"statut": "prive"}),
    "effectif_primaire_urbain": ("Feuil3 T3", {"milieu": "urbain"}),
    "effectif_primaire_rural": ("Feuil3 T3", {"milieu": "rural"}),
    **{f"effectif_{c.lower()}": ("Feuil4 T4", {"classe": c}) for c in _CLASSES},
    **{f"effectif_{c.lower()}_public": ("Feuil4 T4", {"statut": "public", "classe": c}) for c in _CLASSES},
    "effectif_prescolaire_public": ("PRESCOLAIRE T2", {"statut": "public"}),
    "effectif_prescolaire_prive": ("PRESCOLAIRE T2", {"statut": "prive"}),
    "effectif_prescolaire_communautaire": ("PRESCOLAIRE T2", {"statut": "communautaire"}),
    "effectif_prescolaire_urbain": ("PRESCOLAIRE T3", {"milieu": "urbain"}),
    "effectif_prescolaire_rural": ("PRESCOLAIRE T3", {"milieu": "rural"}),
    **{f"effectif_{s.split()[0]}_section": ("PRESCOLAIRE T4", {"classe": s})
       for s in ["petite section", "moyenne section", "grande section"]},
}

_DEFAUTS = {"sexe": "T", "statut": "total", "milieu": "total", "classe": "total"}


def _extraire(table: pd.DataFrame, definitions: dict) -> pd.DataFrame:
    colonnes = []
    for nom, (tableau, filtre) in definitions.items():
        partie = table[table["tableau"] == tableau]
        for dimension, valeur in {**_DEFAUTS, **filtre}.items():
            partie = partie[partie[dimension] == valeur]
        colonnes.append(partie.set_index(["entite_pcode", "annee_scolaire"])["valeur"].rename(nom))
    return pd.concat(colonnes, axis=1)


def construire_panel_region() -> pd.DataFrame:
    """Tous les indicateurs régionaux de la base principale : 13 régions et le pays, 2015-2016 à 2024-2025."""
    large = _extraire(lire("fait_base_principale"), _REGIONAL)
    large["part_filles_primaire"] = large["effectif_primaire_filles"] / large["effectif_primaire"]
    large["part_ecoles_privees"] = large["ecoles_primaires_privees"] / large["ecoles_primaires"]
    large["eleves_par_ecole"] = large["effectif_primaire"] / large["ecoles_primaires"]
    large["prescolaire_pour_100_nouveaux_cp1"] = 100 * large["effectif_prescolaire"] / large["nouveaux_inscrits_cp1"]
    large = large.reset_index().rename(columns={"entite_pcode": "region_ancienne_pcode"})
    regions = lire("region_ancienne")[["region_ancienne_pcode", "region_ancienne_nom"]]
    large = regions.merge(large, on="region_ancienne_pcode", how="right")
    large["region_ancienne_nom"] = large["region_ancienne_nom"].fillna("Burkina Faso")
    flottants = large.select_dtypes("float").columns
    large[flottants] = large[flottants].round(4)
    return large.sort_values(["region_ancienne_pcode", "annee_scolaire"]).reset_index(drop=True)


def construire_serie_nationale() -> pd.DataFrame:
    """Ventilations nationales de la base principale : statut, milieu, classe, sections du préscolaire."""
    large = _extraire(lire("fait_base_principale"), _NATIONAL).reset_index().drop(columns="entite_pcode")
    regional = construire_panel_region()
    pays = regional[regional["region_ancienne_pcode"] == "BF"].drop(columns=["region_ancienne_pcode",
                                                                             "region_ancienne_nom"])
    large = pays.merge(large, on="annee_scolaire", how="outer")
    large["part_prive_primaire"] = large["effectif_primaire_prive"] / large["effectif_primaire"]
    large["part_urbain_primaire"] = large["effectif_primaire_urbain"] / large["effectif_primaire"]
    large["rapport_cm2_cp1_national"] = large["effectif_cm2"] / large["effectif_cp1"]
    flottants = large.select_dtypes("float").columns
    large[flottants] = large[flottants].round(4)
    return large.sort_values("annee_scolaire").reset_index(drop=True)


def _contexte_regional() -> pd.DataFrame:
    """Contexte de la région pour chaque année t ; la réussite au CEP est celle de la session précédente.

    La session du CEP d'une année scolaire a lieu à sa fin : celle de t n'est pas connue à la
    rentrée de t, d'où le décalage d'un an.
    """
    region = construire_panel_region()
    region = region[region["region_ancienne_pcode"] != "BF"]
    contexte = region[["region_ancienne_pcode", "annee_scolaire", "tba", "tbs", "taux_achevement", "ips_tbs",
                       "ips_tap", "tbs_prescolaire", "part_ecoles_privees"]].rename(columns={
        "tba": "tba_region", "tbs": "tbs_region", "taux_achevement": "taux_achevement_region",
        "ips_tbs": "ips_tbs_region", "ips_tap": "ips_tap_region", "tbs_prescolaire": "tbs_prescolaire_region",
        "part_ecoles_privees": "part_ecoles_privees_region"})
    cep = region[["region_ancienne_pcode", "annee_scolaire", "reussite_cep"]].copy()
    cep["annee_scolaire"] = cep["annee_scolaire"].map(lambda a: annee_scolaire(debut(a) + 1))
    return contexte.merge(cep.rename(columns={"reussite_cep": "reussite_cep_precedente_region"}),
                          on=["region_ancienne_pcode", "annee_scolaire"], how="outer")


def _non_formelle_et_prescolaire() -> pd.DataFrame:
    """Éducation non formelle et préscolaire par province, connus à la rentrée de t.

    La campagne d'éducation non formelle Y est achevée à la rentrée de l'année scolaire
    Y-(Y+1) : elle est rattachée à cette année (campagnes 2018, 2019, 2020 et 2024).
    Le préscolaire de t est recensé à la rentrée de t (2023-2024 et 2024-2025).
    """
    enf = lire("fait_enf_province")
    enf = enf[(enf["niveau_geo"] == "province_ancienne") & (enf["milieu"] == "total")]
    enf = enf.assign(annee_scolaire=enf["campagne"].map(annee_scolaire))[
        ["entite_pcode", "annee_scolaire", "adolescents", "centres_adolescents"]].rename(
        columns={"adolescents": "adolescents_non_formelle", "centres_adolescents": "centres_non_formelle_adolescents"})
    pre = lire("fait_prescolaire_province")
    pre = pre[(pre["niveau_geo"] == "province_ancienne") & (pre["sexe"] == "T")][
        ["entite_pcode", "annee_scolaire", "taux_prescolarisation", "grande_section"]].rename(
        columns={"taux_prescolarisation": "taux_prescolarisation_province", "grande_section": "grande_section_province"})
    resultat = enf.merge(pre, on=["entite_pcode", "annee_scolaire"], how="outer")
    return resultat.rename(columns={"entite_pcode": "province_ancienne_pcode"})


# Caractéristiques structurelles mesurées au recensement de 2019 : variable du RGPH -> colonne du panel.
STRUCTURELLES = {"incidence_pauvrete": "pauvrete_province", "profondeur_pauvrete": "profondeur_pauvrete_province", "emploi_7_14": "travail_enfants_7_14_province", "hors_ecole_6_11": "hors_ecole_6_11_province", "hors_ecole_12_15": "hors_ecole_12_15_province", "filles_17_ans_mariees": "filles_17_ans_mariees_province", "alphabetisation_15_64": "alphabetisation_adultes_province", "acte_naissance": "acte_naissance_province", "ratio_filles_garcons_primaire": "parite_scolarisation_province", "electricite": "electricite_province", "telephone": "telephone_province"}


def _structurelles() -> pd.DataFrame:
    """Pauvreté, conditions de vie, consommation et inégalités de la province en 2019, identiques chaque année."""
    vie = lire("fait_conditions_vie")
    vie = vie[vie["niveau_geo"] == "province_ancienne"]
    vie = vie[["entite_pcode", *STRUCTURELLES]].rename(columns=STRUCTURELLES)
    profils = lire("fait_profils_pauvrete")
    profils = profils[profils["niveau_geo"] == "province_ancienne"][
        ["entite_pcode", "consommation_par_personne", "gini", "rapport_q90_q10"]].rename(columns={
        "consommation_par_personne": "consommation_par_personne_province", "gini": "gini_province",
        "rapport_q90_q10": "rapport_q90_q10_province"})
    return vie.merge(profils, on="entite_pcode", how="left").rename(columns={"entite_pcode": "province_ancienne_pcode"})


def _conditions_scolarisation() -> pd.DataFrame:
    """Équipement, distance, taille des écoles, manuels, salles, taux et CEP par province, édition de l'année t."""
    table = lire("fait_conditions_scolarisation")
    ensemble = table[table["sous_tableau"] == "ensemble"]
    large = ensemble.pivot_table(index=["entite_pcode", "annee_scolaire"], columns=["section", "variable"], values="valeur")
    v = lambda section, variable: large.get((section, variable))  # noqa: E731
    resultat = pd.DataFrame(index=large.index)
    ecoles = v("equipement", "ecoles")
    for nom, colonne in [("cantine", "ecoles_cantines"), ("latrines", "ecoles_latrines"),
                         ("eau_potable", "ecoles_eau_potable"), ("electricite", "ecoles_electricite")]:
        resultat[f"part_ecoles_{nom}"] = v("equipement", colonne) / ecoles
    resultat["part_eleves_plus_3km"] = v("distance", "pct_eleves_3_5km") + v("distance", "pct_eleves_plus_5km")
    petites = sum(v("taille_ecoles", f"ecoles_{n}_salles") for n in ["0", "1", "2", "3", "4", "5"])
    resultat["part_ecoles_cycle_incomplet"] = petites / v("taille_ecoles", "ecoles")
    resultat["logements_pour_100_maitres"] = 100 * v("logements_maitres", "logements") / v("logements_maitres", "maitres")
    resultat["manuels_lecture_par_eleve"] = v("manuels", "manuels_lecture") / v("manuels", "eleves")
    resultat["manuels_calcul_par_eleve"] = v("manuels", "manuels_calcul") / v("manuels", "eleves")
    resultat["deficit_places_assises"] = v("mobilier", "deficit_places_assises")
    professions = large.xs("profession_parents", axis=1, level="section")
    resultat["part_parents_agriculteurs"] = (professions["parents_cultivateurs"] + professions["parents_eleveurs"]) / \
        professions.sum(axis=1, min_count=1)
    resultat["part_salles_murs_precaires"] = (v("murs", "murs_semi_dur") + v("murs", "murs_paille_banco")) / v("murs", "salles")
    absent = v("toitures", "toit_absent")
    resultat["part_salles_toit_precaire"] = (v("toitures", "toit_banco") + v("toitures", "toit_paille")
                                             + (absent.fillna(0) if absent is not None else 0)) / v("toitures", "salles")
    resultat["part_salles_recentes"] = v("anciennete_salles", "salles_apres_2015") / v("anciennete_salles", "salles")
    for section in ["tba", "tbs", "tns"]:
        resultat[f"{section}_province"] = v(section, "taux_t")
    resultat["ecart_tbs_filles_garcons"] = v("tbs", "taux_f") - v("tbs", "taux_g")
    resultat["achevement_province"] = v("achevement", "taux_t")
    resultat = resultat.reset_index()
    # CEP : la session de t a lieu en fin d'année ; on retient celle qui clôt t-1.
    cep = v("cep", "taux_t").rename("reussite_cep_precedente_province").reset_index()
    cep["annee_scolaire"] = cep["annee_scolaire"].map(lambda a: annee_scolaire(debut(a) + 1))
    resultat = resultat.merge(cep, on=["entite_pcode", "annee_scolaire"], how="outer")
    return resultat.rename(columns={"entite_pcode": "province_ancienne_pcode"})


def _repartitions() -> pd.DataFrame:
    """Retard scolaire, entrée tardive au CP1, part des enseignantes et des débutants, édition de l'année t."""
    table = lire("fait_repartitions_province")
    ensemble = table[table["sous_tableau"] == "ensemble"]
    cles = ["entite_pcode", "annee_scolaire"]

    def ligne(section: str, modalite: str) -> pd.DataFrame:
        partie = ensemble[(ensemble["section"] == section) & (ensemble["modalite"] == modalite)]
        return partie.pivot_table(index=cles, columns="variable", values="valeur")

    eleves = ligne("ages_eleves", "T")
    entrants = ligne("ages_entrants", "T")
    femmes, total = ligne("enseignants", "F"), ligne("enseignants", "T")
    resultat = pd.DataFrame({
        "part_eleves_12_ans_et_plus": eleves[["age_12", "age_13", "age_14", "age_15", "age_plus_15"]].sum(axis=1)
        / eleves["age_total"],
        "part_entrants_cp1_8_ans_et_plus": entrants[["age_8", "age_9", "age_10", "age_plus_10"]].sum(axis=1)
        / entrants["age_total"],
        "part_enseignantes": femmes["total"] / total["total"],
        "part_enseignants_debutants": total["experience_1_5"] / total["total"],
    })
    return resultat.reset_index().rename(columns={"entite_pcode": "province_ancienne_pcode"})


def construire_panel() -> pd.DataFrame:
    effectifs = _effectifs()
    flux = _flux(effectifs)
    structure = _structure(effectifs)
    provinces = lire("province_ancienne")[["province_ancienne_pcode", "province_ancienne_nom",
                                           "region_ancienne_pcode", "region_ancienne_nom", "provinces_actuelles"]]
    annees = [annee_scolaire(a) for a in range(debut(PREMIERE_ANNEE), 2025)]
    panel = provinces.merge(pd.DataFrame({"annee_scolaire": annees}), how="cross")

    # Cible : passage de t vers t+1.
    cible = flux[["province_ancienne_pcode", "annee_scolaire", "taux_abandon", "effectif_t"]].rename(
        columns={"taux_abandon": "abandon_brut_suivant"})
    panel = panel.merge(cible.drop(columns="effectif_t"), on=["province_ancienne_pcode", "annee_scolaire"], how="left")

    # Variables du passage précédent (t-1 vers t), connues à la date t.
    precedent = flux.assign(annee_scolaire=flux["annee_scolaire"].map(lambda a: annee_scolaire(debut(a) + 1)))
    precedent = precedent[["province_ancienne_pcode", "annee_scolaire", "taux_abandon", "taux_redoublement",
                           "taux_promotion"]].rename(columns={"taux_abandon": "abandon_precedent",
                                                              "taux_redoublement": "redoublement_precedent",
                                                              "taux_promotion": "promotion_precedente"})
    panel = panel.merge(precedent, on=["province_ancienne_pcode", "annee_scolaire"], how="left")

    # Structure et évolution des effectifs.
    panel = panel.merge(structure, on=["province_ancienne_pcode", "annee_scolaire"], how="left")
    effectif = structure.set_index(["province_ancienne_pcode", "annee_scolaire"])["effectif"]
    def effectif_decale(ligne, ecart):
        return effectif.get((ligne["province_ancienne_pcode"], annee_scolaire(debut(ligne["annee_scolaire"]) + ecart)),
                            np.nan)
    panel["effectif_precedent"] = panel.apply(effectif_decale, axis=1, ecart=-1)
    panel["effectif_suivant"] = panel.apply(effectif_decale, axis=1, ecart=1)
    panel["evolution_effectifs"] = panel["effectif"] / panel["effectif_precedent"] - 1
    panel["evolution_effectifs_suivante"] = panel["effectif_suivant"] / panel["effectif"] - 1
    panel["choc_effectifs"] = panel["evolution_effectifs"].abs() > SEUIL_RUPTURE

    # Rupture de scolarisation : la cible n'est plus un taux d'abandon.
    panel["rupture_cible"] = panel["evolution_effectifs_suivante"].abs() > SEUIL_RUPTURE
    panel["abandon_suivant"] = panel["abandon_brut_suivant"].where(~panel["rupture_cible"])
    panel["statut_cible"] = np.select(
        [panel["abandon_brut_suivant"].isna(), panel["rupture_cible"]],
        ["à prévoir", "rupture de scolarisation"], default="abandon observé")

    # Offre scolaire, déplacés, écoles fermées.
    panel = panel.merge(_offre(), on=["province_ancienne_pcode", "annee_scolaire"], how="left")
    panel = panel.merge(_deplaces_a_la_rentree(), on=["province_ancienne_pcode", "annee_scolaire"], how="left")
    panel["deplaces_pour_100_eleves"] = 100 * panel["deplaces"] / panel["effectif"]
    fermees_provinces, fermees_regions = _ecoles_fermees()
    panel = panel.merge(fermees_provinces, on=["province_ancienne_pcode", "annee_scolaire"], how="left")
    panel = panel.merge(fermees_regions, on=["region_ancienne_pcode", "annee_scolaire"], how="left")

    # Contexte régional de la base principale DGESS.
    panel = panel.merge(_contexte_regional(), on=["region_ancienne_pcode", "annee_scolaire"], how="left")

    # Éducation non formelle (seconde chance des déscolarisés) et préscolaire, par province.
    panel = panel.merge(_non_formelle_et_prescolaire(), on=["province_ancienne_pcode", "annee_scolaire"], how="left")
    panel["adolescents_non_formelle_pour_1000_eleves"] = 1000 * panel["adolescents_non_formelle"] / panel["effectif"]

    # Conditions de scolarisation de l'année t (annuaires DGESS, 8 éditions).
    panel = panel.merge(_conditions_scolarisation(), on=["province_ancienne_pcode", "annee_scolaire"], how="left")
    panel["deficit_places_pour_100_eleves"] = 100 * panel.pop("deficit_places_assises") / panel["effectif"]
    panel = panel.merge(_repartitions(), on=["province_ancienne_pcode", "annee_scolaire"], how="left")

    # Pauvreté et conditions de vie (RGPH 2019) : caractéristiques structurelles, constantes dans le temps.
    panel = panel.merge(_structurelles(), on="province_ancienne_pcode", how="left")

    colonnes_arrondies = panel.select_dtypes("float").columns
    panel[colonnes_arrondies] = panel[colonnes_arrondies].round(4)
    return panel.sort_values(["province_ancienne_pcode", "annee_scolaire"]).reset_index(drop=True)


def construire_panel_mensuel() -> pd.DataFrame:
    """Déplacés par province et par mois, avec l'évolution sur un mois et sur trois mois (alerte avant l'annuaire)."""
    pdi = deplaces_par_province()
    pdi["mois"] = pdi["date_situation"].str[:7]
    mensuel = (pdi.sort_values("date_situation").groupby(["province_ancienne_pcode", "mois"], as_index=False)
               .last())
    mensuel = mensuel.sort_values(["province_ancienne_pcode", "mois"])
    groupes = mensuel.groupby("province_ancienne_pcode")["deplaces"]
    mensuel["variation_un_releve"] = groupes.pct_change().round(4)
    mensuel["variation_trois_releves"] = groupes.pct_change(3).round(4)

    regions = lire("fait_esu_region")
    regions["mois"] = regions["mois"].str[:7]
    provinces = lire("province_ancienne")[["province_ancienne_pcode", "region_ancienne_pcode"]]
    mensuel = mensuel.merge(provinces, on="province_ancienne_pcode", how="left")
    mensuel = mensuel.merge(regions[["region_ancienne_pcode", "mois", "etablissements_fermes", "eleves_affectes"]]
                            .rename(columns={"etablissements_fermes": "ecoles_fermees_region",
                                             "eleves_affectes": "eleves_affectes_region"}),
                            on=["region_ancienne_pcode", "mois"], how="left")
    return mensuel[["province_ancienne_pcode", "region_ancienne_pcode", "mois", "date_situation", "deplaces",
                    "enfants_deplaces", "variation_un_releve", "variation_trois_releves", "ecoles_fermees_region",
                    "eleves_affectes_region"]].reset_index(drop=True)
