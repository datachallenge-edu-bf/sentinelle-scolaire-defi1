"""Démographie annuelle de la Sentinelle : population par âge des communes, de 2016 à 2025.

Les projections actualisées de l'INSD donnent la population par commune, âge simple et sexe
de 2020 à 2025 (table ``fait_population``). Le panel commence en 2016-2017 : les années 2016 à
2019 sont reconstituées par rétroprojection des cohortes. Pour chaque commune et chaque sexe,
le vecteur des âges de l'année t est celui de t + 1 décalé d'un an, divisé par la survie de
chaque âge tirée des projections nationales (N(a + 1, 2021) / N(a, 2020)) ; le groupe ouvert
(79 ans, 80 ans et plus) suit l'évolution nationale du même âge. Les mouvements de population
ne sont pas représentés. La colonne ``methode_population`` dit si la valeur est publiée ou
rétroprojetée.

Les groupes d'âge de l'école et les indicateurs démographiques sont calculés par commune puis
sommés : sur les provinces et régions de 2025 comme sur les anciennes, les communes s'emboîtant
dans les deux découpages.
"""

from __future__ import annotations

from functools import lru_cache, cache

import numpy as np
import pandas as pd

from .panel import annee_scolaire, lire

PREMIERE, DERNIERE = 2016, 2025
GROUPES = {"population_totale": (0, 80), "moins_15": (0, 14), "age_15_64": (15, 64), "plus_64": (65, 80),
           "enfants_3_5": (3, 5), "enfants_5": (5, 5), "enfants_6_11": (6, 11), "enfants_12_15": (12, 15),
           "jeunes_16_18": (16, 18)}
SEXES_DETAILLES = ("enfants_6_11", "enfants_12_15")


def _survie(pays: pd.DataFrame) -> dict[str, np.ndarray]:
    """Survie d'un âge au suivant, pour chaque sexe, d'après les projections nationales de 2020 et 2021."""
    survie = {}
    for sexe in ("G", "F", "T"):
        n20 = pays[(pays["annee"] == 2020) & (pays["sexe"] == sexe)].set_index("age")["population"].reindex(range(81))
        n21 = pays[(pays["annee"] == 2021) & (pays["sexe"] == sexe)].set_index("age")["population"].reindex(range(81))
        s = np.empty(81)
        s[:79] = n21.to_numpy()[1:80] / n20.to_numpy()[:79]
        s[79:] = n21.to_numpy()[79:] / n20.to_numpy()[79:]
        survie[sexe] = s
    return survie


@lru_cache(maxsize=1)
def population_communes() -> pd.DataFrame:
    """Commune × année (2016-2025) × sexe : un vecteur de 81 âges par ligne, en format long."""
    pop = lire("fait_population")
    pays = pop[pop["niveau_geo"] == "pays"]
    communes = pop[pop["niveau_geo"] == "commune"]
    survie = _survie(pays)
    cube = communes.pivot_table(index=["entite_pcode", "sexe", "annee"], columns="age", values="population")
    cube = cube.reindex(columns=range(81))
    morceaux = [cube.reset_index().assign(methode_population="projection publiée")]
    suivant = cube.xs(2020, level="annee")
    for annee in range(2019, PREMIERE - 1, -1):
        s = np.vstack([survie[x] for x in suivant.index.get_level_values("sexe")])
        valeurs = suivant.to_numpy()
        precedent = np.empty_like(valeurs)
        precedent[:, :79] = valeurs[:, 1:80] / s[:, :79]          # cohortes : âge a en t = âge a + 1 en t + 1
        precedent[:, 79:] = valeurs[:, 79:] / s[:, 79:]           # groupe ouvert : évolution du même âge
        suivant = pd.DataFrame(precedent, index=suivant.index, columns=suivant.columns)
        morceaux.append(suivant.reset_index().assign(annee=annee, methode_population="rétroprojection par cohortes"))
    large = pd.concat(morceaux, ignore_index=True)
    return large[large["annee"].between(PREMIERE, DERNIERE)]


def _groupes(table: pd.DataFrame, cles: list[str]) -> pd.DataFrame:
    sortie = {}
    for nom, (a, b) in GROUPES.items():
        somme = table[list(range(a, b + 1))].sum(axis=1)
        par_sexe = table.assign(_v=somme).groupby(cles + ["sexe"])["_v"].sum().unstack("sexe")
        sortie[nom] = par_sexe["T"]
        if nom in SEXES_DETAILLES:
            sortie[f"{nom}_filles"], sortie[f"{nom}_garcons"] = par_sexe["F"], par_sexe["G"]
    resultat = pd.DataFrame(sortie)
    resultat["methode_population"] = table.groupby(cles)["methode_population"].first()
    resultat["rapport_dependance"] = 100 * (resultat["moins_15"] + resultat["plus_64"]) / resultat["age_15_64"]
    resultat["part_moins_15"] = 100 * resultat["moins_15"] / resultat["population_totale"]
    return resultat


@cache
def demographie(niveau: str) -> pd.DataFrame:
    """Groupes d'âge et indicateurs par entité (commune, province ou région, de 2025 ou anciennes) et année scolaire.

    ``niveau`` est une colonne de la table des communes : commune_pcode, province_pcode, region_pcode,
    province_ancienne_pcode ou region_ancienne_pcode.
    """
    pop = population_communes()
    if niveau != "commune_pcode":
        lien = lire("commune").set_index("commune_pcode")[niveau]
        pop = pop.assign(entite_pcode=pop["entite_pcode"].map(lien))
    numeriques = list(range(81))
    if niveau in {"region_pcode", "region_ancienne_pcode"}:
        # Ligne du pays (BF) des panels régionaux : somme de toutes les communes.
        national = pop.groupby(["annee", "sexe"])[numeriques].sum().reset_index()
        national["entite_pcode"] = "BF"
        national["methode_population"] = pop.groupby(["annee", "sexe"])["methode_population"].first().to_numpy()
        pop = pd.concat([pop, national], ignore_index=True)
    agregee = pop.groupby(["entite_pcode", "annee", "sexe"])[numeriques].sum().reset_index()
    agregee["methode_population"] = pop.groupby(["entite_pcode", "annee", "sexe"])["methode_population"].first().to_numpy()
    resultat = _groupes(agregee, ["entite_pcode", "annee"]).reset_index()
    resultat = resultat.sort_values(["entite_pcode", "annee"])
    precedent = resultat.groupby("entite_pcode")["enfants_6_11"].shift(1)
    resultat["croissance_enfants_6_11"] = 100 * (resultat["enfants_6_11"] / precedent - 1)
    resultat["annee_scolaire"] = resultat["annee"].map(annee_scolaire)
    return resultat.drop(columns="annee").rename(columns={"entite_pcode": niveau})


def ajouter(table: pd.DataFrame, niveau: str) -> pd.DataFrame:
    """Joint la démographie à une table indexée par ``niveau`` et ``annee_scolaire``."""
    demo = demographie(niveau)
    deja = [c for c in demo.columns if c in table.columns and c not in (niveau, "annee_scolaire")]
    return table.merge(demo.drop(columns=deja), on=[niveau, "annee_scolaire"], how="left")


def valider() -> dict[str, float]:
    """Rétroprojection appliquée au pays, comparée aux anciennes projections nationales (base RGPH 2006)."""
    pop = lire("fait_population")
    pays = pop[pop["niveau_geo"] == "pays"]
    survie = _survie(pays)
    vecteur = pays[(pays["annee"] == 2020) & (pays["sexe"] == "T")].set_index("age")["population"].reindex(range(81)).to_numpy()
    ecarts = {}
    for annee in range(2019, 2015, -1):
        precedent = np.empty(81)
        precedent[:79] = vecteur[1:80] / survie["T"][:79]
        precedent[79:] = vecteur[79:] / survie["T"][79:]
        vecteur = precedent
        if annee <= 2018:
            ancien = pays[(pays["annee"] == annee) & (pays["sexe"] == "T")].set_index("age")["population"]
            ecarts[annee] = float(vecteur[6:12].sum() / ancien.loc[6:11].sum())
    return ecarts


def _insd_communes() -> pd.DataFrame:
    """Effectifs communaux des annuaires de l'INSD : une colonne par grandeur (modalité ensemble)."""
    insd = lire("fait_insd_commune")
    ensemble = insd[insd["modalite"] == "T"]
    def serie(indicateurs):
        partie = ensemble[ensemble["indicateur"].isin(indicateurs)]
        partie = partie.assign(rang=partie["indicateur"].map({k: i for i, k in enumerate(indicateurs)}))
        return partie.sort_values("rang").drop_duplicates(["commune_pcode", "annee_scolaire"]).set_index(
            ["commune_pcode", "annee_scolaire"])["valeur"]
    return pd.DataFrame({
        "eleves_primaire_insd": serie(["eleves_par_sexe", "eleves_par_statut"]),
        "enseignants_primaire_insd": serie(["enseignants_par_sexe", "enseignants_par_statut"]),
        "salles_primaire_insd": serie(["salles"]),
        "salles_primaire_paillote_insd": serie(["salles_paillote"]),
        "ecoles_primaires_fermees_insd": serie(["ecoles_fermees"]),
        "eleves_post_primaire_insd": serie(["eleves_post_primaire_par_statut", "eleves_post_primaire_par_sexe"]),
    }).reset_index()


def _deplaces_communes() -> pd.DataFrame:
    """Déplacés par commune : dernière situation des six mois précédant le 31 décembre de l'année de rentrée."""
    pdi = lire("fait_pdi_commune")
    pdi["date"] = pd.to_datetime(pdi["date_situation"])
    lignes = []
    for annee in range(PREMIERE, DERNIERE):
        borne = pd.Timestamp(f"{annee}-12-31")
        fenetre = pdi[(pdi["date"] <= borne) & (pdi["date"] > borne - pd.DateOffset(months=6))]
        if not fenetre.empty:
            derniere = fenetre[fenetre["date"] == fenetre["date"].max()]
            lignes.append(derniere.assign(annee_scolaire=annee_scolaire(annee)))
    if not lignes:
        return pd.DataFrame(columns=["commune_pcode", "annee_scolaire", "deplaces"])
    return pd.concat(lignes).rename(columns={"pdi_total": "deplaces"})[["commune_pcode", "annee_scolaire", "deplaces"]]


def panel_communes() -> pd.DataFrame:
    """Commune × année scolaire (2016-2017 à 2024-2025) : base de la carte communale de vulnérabilité."""
    communes = lire("commune")[["commune_pcode", "commune_nom", "province_pcode", "province_nom", "region_pcode",
                                "region_nom", "province_ancienne_pcode", "province_ancienne_nom",
                                "region_ancienne_pcode", "region_ancienne_nom"]]
    annees = pd.DataFrame({"annee_scolaire": [annee_scolaire(a) for a in range(PREMIERE, DERNIERE)]})
    panel = communes.merge(annees, how="cross")
    panel = panel.merge(_insd_communes(), on=["commune_pcode", "annee_scolaire"], how="left")
    panel = ajouter(panel, "commune_pcode")
    panel = panel.merge(_deplaces_communes(), on=["commune_pcode", "annee_scolaire"], how="left")
    from . import recensement
    panel = panel.merge(recensement.commune(), on="commune_pcode", how="left")
    # Taux et rapports communaux : élèves comptés dans la commune de l'école.
    panel["tbs_primaire_commune"] = 100 * panel["eleves_primaire_insd"] / panel["enfants_6_11"]
    panel["tbs_post_primaire_commune"] = 100 * panel["eleves_post_primaire_insd"] / panel["enfants_12_15"]
    panel["eleves_par_enseignant_primaire_insd"] = panel["eleves_primaire_insd"] / panel["enseignants_primaire_insd"].where(
        panel["enseignants_primaire_insd"] > 0)
    panel["part_salles_primaire_paillote_insd"] = panel["salles_primaire_paillote_insd"] / panel[
        "salles_primaire_insd"].where(panel["salles_primaire_insd"] > 0)
    panel["deplaces_pour_100_habitants"] = 100 * panel["deplaces"] / panel["population_totale"]
    precedent = panel.groupby("commune_pcode")["eleves_primaire_insd"].shift(1)
    panel["evolution_eleves_primaire_insd"] = 100 * (panel["eleves_primaire_insd"] / precedent - 1)
    flottants = panel.select_dtypes("float").columns
    panel[flottants] = panel[flottants].round(4)
    return panel.sort_values(["commune_pcode", "annee_scolaire"]).reset_index(drop=True)
