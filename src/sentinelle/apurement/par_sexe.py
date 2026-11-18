"""Base apurée par sexe : 47 provinces × 9 années scolaires × filles et garçons.

Les annuaires publient par sexe les flux, les effectifs, les taux de scolarisation,
l'achèvement, le CEP et l'âge des élèves du primaire, ainsi que les taux et les flux du
post-primaire et du secondaire. Le panel de l'étape 03 n'en garde que l'ensemble ; ce
module construit les mêmes variables pour chaque sexe.

Chaque valeur d'un sexe est ancrée sur la valeur de l'ensemble de la base apurée :

    valeur(sexe) = valeur(ensemble, base apurée) + écart(sexe)

où l'écart (sexe − ensemble, ou rapport sexe / ensemble pour les effectifs) est mesuré
dans la même source, la même année, pour l'ancienne province. Quand l'ensemble est observé,
la valeur du sexe est exactement la valeur publiée. Quand l'ensemble a été imputé, ou que
la répartition par sexe manque, l'écart de l'année observée la plus proche est reporté : la
valeur du sexe hérite de l'imputation de l'ensemble et reste cohérente avec elle. Les
provinces scindées en 2025 prennent l'écart de leur province d'origine.

Le secondaire n'a pas d'ensemble dans la base apurée : ses séries par sexe sont complétées
par interpolation (2019-2020) et par report de l'année publiée la plus proche.

Les variables sans détail par sexe (école, encadrement, recensement, contexte régional)
sont reprises de la base apurée, identiques pour les deux sexes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config
from ..indicateurs import flux_par_classe, taux
from ..transformation.decoupage_2025 import _communes, correspondance_provinces
from ..transformation.panel import SEUIL_RUPTURE, annee_scolaire, debut, lire
from . import selection
from .etat import IMPUTEE, OBSERVEE

SEXES = ["F", "G"]
ANNEES = [annee_scolaire(a) for a in range(2016, 2025)]
CLES = ["province_ancienne_pcode", "annee_scolaire", "sexe"]

# Variables par sexe ancrées sur la base apurée : nom -> mode de l'écart.
ANCREES = {
    "abandon_primaire_precedent": "difference", "redoublement_primaire_precedent": "difference",
    "promotion_primaire_precedente": "difference", "eleves_primaire": "rapport",
    "evolution_eleves_primaire": "difference", "part_cp1": "difference", "rapport_cm2_cp1": "difference",
    "tba_primaire_province": "difference", "tbs_primaire_province": "difference",
    "tns_primaire_province": "difference", "achevement_primaire_province": "difference",
    "reussite_cep_precedente_province": "difference", "part_eleves_primaire_12_ans_et_plus": "difference",
    "part_entrants_cp1_8_ans_et_plus": "difference", "tba_6e_province": "difference",
    "tbs_post_primaire_province": "difference", "achevement_post_primaire_province": "difference",
    "abandon_post_primaire_province": "difference", "redoublement_3e_province": "difference",
}
# Variables du secondaire, sans ensemble dans la base apurée.
SECONDAIRE = ["tba_2nde_province", "tbs_secondaire_province", "achevement_secondaire_province",
              "abandon_secondaire_province", "redoublement_terminale_province"]
# Variables recalculées à partir des précédentes.
DERIVEES = ["choc_eleves_primaire", "ecart_achevement_primaire_entree_6e"]
PAR_SEXE = list(ANCREES) + DERIVEES + SECONDAIRE
PROPORTIONS = ["part_cp1", "part_eleves_primaire_12_ans_et_plus", "part_entrants_cp1_8_ans_et_plus"]
# Bornes de recodage des taux de flux, comme pour l'ensemble.
BORNES_FLUX = (-5, 105)
FLUX = ["abandon_primaire_precedent", "redoublement_primaire_precedent", "promotion_primaire_precedente"]
# Annuaire 2024-2025 : la répartition des effectifs par sexe est invraisemblable dans 31 provinces sur 45
# (70 % de filles au Kadiogo contre 51 % en 2023-2024) et, dans les 14 autres, l'écart d'abandon
# filles − ensemble qui en découle va de −10 à +8 points (−3 à 0 les autres années). Les effectifs
# par sexe de cette édition ne sont pas utilisés ; les taux publiés par sexe (TBS, achèvement, CEP, âges)
# viennent d'autres tableaux et restent retenus.
EFFECTIFS_SEXE_DOUTEUX = {"2024-2025"}


# Lecture des sources, par ancienne province, sexe (F, G, T) et année.

def _long(table: pd.DataFrame, colonnes: dict[str, str]) -> pd.DataFrame:
    """Table (entite_pcode, annee_scolaire, sexe, colonnes...) renommée selon ``colonnes``."""
    table = table.rename(columns={"entite_pcode": "province_ancienne_pcode", **colonnes})
    return table[["province_ancienne_pcode", "annee_scolaire", "sexe", *colonnes.values()]]


def _effectifs() -> pd.DataFrame:
    eff = lire("fait_effectifs_retenus")
    eff = eff[eff["niveau_geo"] == "province_ancienne"].copy()
    douteux = (eff["sexe"] != "T") & (~eff["repartition_sexe_fiable"].astype(bool)
                                      | eff["annee_scolaire"].isin(EFFECTIFS_SEXE_DOUTEUX))
    eff.loc[douteux, ["effectif", "redoublants"]] = np.nan
    return eff


def _flux_primaire(eff: pd.DataFrame) -> pd.DataFrame:
    """Taux du cycle CP1 à CM1 du passage t-1 vers t, connus à la date t."""
    flux = flux_par_classe(eff.dropna(subset=["effectif"]))
    cycle = taux(flux, ["entite_pcode", "annee_scolaire", "sexe"])
    cycle["annee_scolaire"] = cycle["annee_scolaire"].map(lambda a: annee_scolaire(debut(a) + 1))
    return _long(cycle, {"taux_abandon": "abandon_primaire_precedent",
                         "taux_redoublement": "redoublement_primaire_precedent",
                         "taux_promotion": "promotion_primaire_precedente"})


def _structure(eff: pd.DataFrame) -> pd.DataFrame:
    classes = eff.pivot_table(index=["entite_pcode", "annee_scolaire", "sexe"], columns="niveau", values="effectif")
    s = pd.DataFrame({"eleves_primaire": classes["Total"], "part_cp1": classes["CP1"] / classes["Total"],
                      "rapport_cm2_cp1": classes["CM2"] / classes["CP1"]}).reset_index()
    precedent = s[["entite_pcode", "annee_scolaire", "sexe", "eleves_primaire"]].copy()
    precedent["annee_scolaire"] = precedent["annee_scolaire"].map(lambda a: annee_scolaire(debut(a) + 1))
    s = s.merge(precedent.rename(columns={"eleves_primaire": "precedent"}),
                on=["entite_pcode", "annee_scolaire", "sexe"], how="left")
    s["evolution_eleves_primaire"] = s["eleves_primaire"] / s["precedent"] - 1
    return _long(s, {c: c for c in ["eleves_primaire", "part_cp1", "rapport_cm2_cp1", "evolution_eleves_primaire"]})


def _taux_primaire() -> pd.DataFrame:
    table = lire("fait_conditions_scolarisation")
    table = table[(table["sous_tableau"] == "ensemble") & table["variable"].str.startswith("taux_")]
    table = table.assign(sexe=table["variable"].str[-1].str.upper())
    large = table.pivot_table(index=["entite_pcode", "annee_scolaire", "sexe"], columns="section", values="valeur")
    large = large.reset_index()
    cep = large[["entite_pcode", "annee_scolaire", "sexe", "cep"]].copy()
    cep["annee_scolaire"] = cep["annee_scolaire"].map(lambda a: annee_scolaire(debut(a) + 1))  # session qui clôt t-1
    large = large.drop(columns="cep").merge(cep, on=["entite_pcode", "annee_scolaire", "sexe"], how="outer")
    return _long(large, {"tba": "tba_primaire_province", "tbs": "tbs_primaire_province",
                         "tns": "tns_primaire_province", "achevement": "achevement_primaire_province",
                         "cep": "reussite_cep_precedente_province"})


def _ages() -> pd.DataFrame:
    table = lire("fait_repartitions_province")
    table = table[(table["sous_tableau"] == "ensemble") & table["modalite"].isin(["F", "G", "T"])]
    cles = ["entite_pcode", "annee_scolaire", "modalite"]
    eleves = table[table["section"] == "ages_eleves"].pivot_table(index=cles, columns="variable", values="valeur")
    entrants = table[table["section"] == "ages_entrants"].pivot_table(index=cles, columns="variable", values="valeur")
    resultat = pd.DataFrame({
        "part_eleves_primaire_12_ans_et_plus":
            eleves[["age_12", "age_13", "age_14", "age_15", "age_plus_15"]].sum(axis=1) / eleves["age_total"],
        "part_entrants_cp1_8_ans_et_plus":
            entrants[["age_8", "age_9", "age_10", "age_plus_10"]].sum(axis=1) / entrants["age_total"],
    }).reset_index().rename(columns={"modalite": "sexe"})
    return _long(resultat, {c: c for c in ["part_eleves_primaire_12_ans_et_plus", "part_entrants_cp1_8_ans_et_plus"]})


def _apres_primaire() -> pd.DataFrame:
    """Post-primaire et secondaire de l'année t ; les flux décrivent le passage de t-1 à t."""
    table = lire("fait_secondaire_province")
    table = table[table["niveau"] == "province_ancienne"]
    cles = ["entite_pcode", "annee_scolaire", "sexe"]
    t = table[table["mesure"] == "taux"].pivot_table(index=cles, columns="indicateur", values="valeur")
    f = table[table["indicateur"].str.startswith("flux_")].pivot_table(
        index=cles, columns=["indicateur", "mesure"], values="valeur")
    abandon = f.xs("abandon", axis=1, level="mesure")
    resultat = pd.DataFrame({
        "tba_6e_province": t["tba_6e"], "tbs_post_primaire_province": t["tbs_post_primaire"],
        "achevement_post_primaire_province": t["tach_post_primaire"],
        "abandon_post_primaire_province": abandon[["flux_6e", "flux_5e", "flux_4e"]].mean(axis=1),
        "redoublement_3e_province": f[("flux_3e", "redoublement")],
        "tba_2nde_province": t["tba_2nde"], "tbs_secondaire_province": t["tbs_secondaire"],
        "achevement_secondaire_province": t["tach_secondaire"],
        "abandon_secondaire_province": abandon[["flux_2nde", "flux_1ere"]].mean(axis=1),
        "redoublement_terminale_province": f[("flux_tle", "redoublement")],
    }).reset_index()
    return _long(resultat, {c: c for c in resultat.columns if c not in cles})


def sources_par_sexe() -> pd.DataFrame:
    """Toutes les variables par ancienne province, année et sexe (F, G, T), valeurs publiées seulement."""
    eff = _effectifs()
    tables = [_flux_primaire(eff), _structure(eff), _taux_primaire(), _ages(), _apres_primaire()]
    resultat = tables[0]
    for table in tables[1:]:
        resultat = resultat.merge(table, on=CLES, how="outer")
    return resultat[resultat["annee_scolaire"].isin(ANNEES)].reset_index(drop=True)


# Écarts entre chaque sexe et l'ensemble, dans la même source.

def _ecarts(sources: pd.DataFrame) -> pd.DataFrame:
    s = sources.set_index(CLES)
    ensemble = s.xs("T", level="sexe")
    lignes = []
    for sexe in SEXES:
        valeurs = s.xs(sexe, level="sexe")
        e = pd.DataFrame(index=valeurs.index.union(ensemble.index))
        for variable, mode in ANCREES.items():
            v, total = valeurs[variable].reindex(e.index), ensemble[variable].reindex(e.index)
            if mode == "rapport":
                e[variable] = v / total.where(total > 0)
            else:
                e[variable] = v - total
        lignes.append(e.assign(sexe=sexe).reset_index())
    return pd.concat(lignes, ignore_index=True)


def _ecart_le_plus_proche(serie: pd.Series, annee: str) -> tuple[float, str | None]:
    """Écart de l'année demandée, sinon de l'année observée la plus proche (la plus ancienne en cas d'égalité)."""
    connues = serie.dropna()
    if annee in connues.index:
        return float(connues[annee]), annee
    if connues.empty:
        return np.nan, None
    proche = min(connues.index, key=lambda a: (abs(debut(a) - debut(annee)), debut(a)))
    return float(connues[proche]), proche


# Construction de la base.

def _completer_serie(serie: pd.Series) -> tuple[pd.Series, dict[str, str]]:
    """Interpolation des trous intérieurs, report de l'année publiée la plus proche aux extrémités."""
    methodes = {}
    complete = serie.copy()
    connues = serie.dropna()
    if connues.empty:
        return complete, methodes
    rang = {a: i for i, a in enumerate(ANNEES)}
    for annee in serie.index[serie.isna()]:
        avant = [a for a in connues.index if rang[a] < rang[annee]]
        apres = [a for a in connues.index if rang[a] > rang[annee]]
        if avant and apres:
            a, b = avant[-1], apres[0]
            poids = (rang[annee] - rang[a]) / (rang[b] - rang[a])
            complete[annee] = connues[a] + poids * (connues[b] - connues[a])
            methodes[annee] = f"interpolation linéaire entre {a} et {b}"
        else:
            proche = avant[-1] if avant else apres[0]
            complete[annee] = connues[proche]
            methodes[annee] = f"report de {proche}"
    return complete, methodes


def construire(base: pd.DataFrame, statuts: pd.DataFrame, sources: pd.DataFrame | None = None
               ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Base par sexe et statut de chaque cellule par sexe."""
    sources = sources_par_sexe() if sources is None else sources
    passage = correspondance_provinces(_communes())
    scindees = set(passage.loc[passage["part_population"] < 0.999, "province_pcode"])
    ecarts = _ecarts(sources).set_index(["province_ancienne_pcode", "sexe", "annee_scolaire"]).sort_index()
    valeurs = sources.set_index(["province_ancienne_pcode", "sexe", "annee_scolaire"]).sort_index()
    statut_total = statuts.set_index(["province_pcode", "annee_scolaire", "variable"])["statut"]

    lignes, cellules = [], []
    for r in base.itertuples(index=False):
        d = r._asdict()
        for sexe in SEXES:
            ligne = {c: d[c] for c in selection.IDENTIFIANTS}
            ligne["sexe"] = sexe
            for variable, mode in ANCREES.items():
                total = d[variable]
                cle = (d["province_ancienne_pcode"], sexe)
                serie = ecarts[variable].loc[cle] if cle in ecarts.index else pd.Series(dtype=float)
                ecart, annee_ecart = _ecart_le_plus_proche(serie, d["annee_scolaire"])
                if np.isnan(ecart):
                    medianes = ecarts.xs(sexe, level="sexe")[variable]
                    ecart = float(medianes.xs(d["annee_scolaire"], level="annee_scolaire").median())
                    annee_ecart = "médiane des provinces"
                valeur = total * ecart if mode == "rapport" else total + ecart
                if variable in FLUX:
                    valeur = float(np.clip(valeur, *BORNES_FLUX))
                elif variable in PROPORTIONS:
                    valeur = float(np.clip(valeur, 0, 1))
                elif variable != "evolution_eleves_primaire":
                    valeur = max(float(valeur), 0.0)
                total_observe = statut_total.get((d["province_pcode"], d["annee_scolaire"], variable)) == OBSERVEE
                publie = (cle + (d["annee_scolaire"],)) in valeurs.index and pd.notna(
                    valeurs[variable].get(cle + (d["annee_scolaire"],)))
                observee = (d["province_pcode"] not in scindees and total_observe and publie
                            and annee_ecart == d["annee_scolaire"])
                if observee:
                    valeur = float(valeurs.at[cle + (d["annee_scolaire"],), variable])
                    methode = ""
                elif d["province_pcode"] in scindees:
                    methode = f"ensemble de la province scindée + écart de la province d'origine ({annee_ecart})"
                elif not total_observe:
                    methode = f"ensemble imputé dans la base apurée + écart du sexe ({annee_ecart})"
                else:
                    methode = f"répartition par sexe non publiée : ensemble + écart du sexe ({annee_ecart})"
                ligne[variable] = round(valeur, 4)
                cellules.append((d["province_pcode"], d["province_nom"], d["annee_scolaire"], sexe, variable,
                                 OBSERVEE if observee else IMPUTEE, methode))
            lignes.append(ligne)
    table = pd.DataFrame(lignes)

    # Variables recalculées.
    table["choc_eleves_primaire"] = table["evolution_eleves_primaire"].abs() > SEUIL_RUPTURE
    table["ecart_achevement_primaire_entree_6e"] = table["achevement_primaire_province"] - table["tba_6e_province"]
    statut_cellule = {(p, a, s, v): st for p, _, a, s, v, st, _ in cellules}
    for i, r in table.iterrows():
        for variable, sources_derivee in [("choc_eleves_primaire", ["evolution_eleves_primaire"]),
                                          ("ecart_achevement_primaire_entree_6e",
                                           ["achevement_primaire_province", "tba_6e_province"])]:
            st = [statut_cellule[(r["province_pcode"], r["annee_scolaire"], r["sexe"], v)] for v in sources_derivee]
            observee = all(x == OBSERVEE for x in st)
            cellules.append((r["province_pcode"], r["province_nom"], r["annee_scolaire"], r["sexe"], variable,
                             OBSERVEE if observee else IMPUTEE, "" if observee else "recalculée à partir de valeurs imputées"))

    # Secondaire : séries complétées par sexe, provinces scindées copiées de leur province d'origine.
    for sexe in SEXES:
        for ancienne in table["province_ancienne_pcode"].unique():
            cle = (ancienne, sexe)
            for variable in SECONDAIRE:
                brute = (valeurs[variable].loc[cle] if cle in valeurs.index else pd.Series(dtype=float)).reindex(ANNEES)
                complete, methodes = _completer_serie(brute)
                masque = (table["province_ancienne_pcode"] == ancienne) & (table["sexe"] == sexe)
                for i in table.index[masque]:
                    annee, pcode = table.at[i, "annee_scolaire"], table.at[i, "province_pcode"]
                    table.at[i, variable] = round(float(complete[annee]), 4) if pd.notna(complete[annee]) else np.nan
                    if annee in methodes:
                        statut, methode = IMPUTEE, methodes[annee]
                    else:
                        statut = IMPUTEE if pcode in scindees else OBSERVEE
                        methode = "valeur de la province d'origine" if pcode in scindees else ""
                    cellules.append((pcode, table.at[i, "province_nom"], annee, sexe, variable, statut, methode))

    # Variables sans détail par sexe : reprises de la base apurée.
    communes = [c for c in selection.VARIABLES if c not in PAR_SEXE and c not in ("part_filles_primaire",)]
    table = table.merge(base[["province_pcode", "annee_scolaire", *communes]],
                        on=["province_pcode", "annee_scolaire"], how="left")
    table["cible_observee"] = [statut_cellule.get((p, a, s, "abandon_primaire_precedent")) == OBSERVEE
                               for p, a, s in zip(table["province_pcode"], table["annee_scolaire"], table["sexe"])]
    colonnes = selection.IDENTIFIANTS + ["sexe"] + PAR_SEXE + [c for c in communes if c != "cible_observee"] + \
        ["cible_observee"]
    table = table[colonnes].sort_values(["province_pcode", "annee_scolaire", "sexe"]).reset_index(drop=True)
    statut = pd.DataFrame(cellules, columns=["province_pcode", "province_nom", "annee_scolaire", "sexe", "variable",
                                             "statut", "methode"])
    return table, statut


def controler(table: pd.DataFrame, statut: pd.DataFrame, base: pd.DataFrame, sources: pd.DataFrame) -> pd.DataFrame:
    """Contrôles de la base par sexe."""
    vides = int(table[PAR_SEXE].isna().sum().sum())
    # Les valeurs observées sont celles des sources.
    src = sources.set_index(CLES)
    ancienne = table.set_index(["province_pcode", "annee_scolaire", "sexe"])["province_ancienne_pcode"]
    observees = statut[(statut["statut"] == OBSERVEE) & statut["variable"].isin(list(ANCREES) + SECONDAIRE)]
    t = table.set_index(["province_pcode", "annee_scolaire", "sexe"])
    ecarts = 0
    for r in observees.itertuples():
        k = (r.province_pcode, r.annee_scolaire, r.sexe)
        publie = src[r.variable].get((ancienne[k], r.annee_scolaire, r.sexe))
        ecarts += int(publie is None or pd.isna(publie) or abs(float(publie) - float(t.at[k, r.variable])) > 1e-3)
    # Filles et garçons redonnent l'ensemble : effectifs et abandon du primaire (somme des effectifs).
    eff = t["eleves_primaire"].unstack("sexe")
    total = base.set_index(["province_pcode", "annee_scolaire"])["eleves_primaire"]
    ecart_eff = ((eff["F"] + eff["G"]) / total.reindex(eff.index) - 1).abs()
    eff_src = sources.set_index(CLES)["eleves_primaire"].unstack("sexe").dropna()
    ab = sources.set_index(CLES)["abandon_primaire_precedent"].unstack("sexe")
    poids = sources.set_index(CLES)["eleves_primaire"].unstack("sexe")
    pondere = (ab["F"] * poids["F"] + ab["G"] * poids["G"]) / (poids["F"] + poids["G"])
    ecart_ab = (pondere - ab["T"]).abs().dropna()
    compte = statut.groupby("statut").size()
    resultats = [
        ("aucune_cellule_vide", vides == 0, f"{len(table)} lignes × {len(PAR_SEXE)} variables par sexe, {vides} vide(s)"),
        ("valeurs_observees_egales_aux_sources", ecarts == 0,
         f"{len(observees)} cellules observées comparées aux annuaires : {ecarts} écart(s)"),
        ("filles_plus_garcons_egal_ensemble_effectifs", bool((ecart_eff <= 0.01).mean() >= 0.95),
         f"F + G à 1 % de l'ensemble de la base apurée pour {int((ecart_eff <= 0.01).sum())} lignes sur "
         f"{len(ecart_eff)} ; dans les annuaires : {int(((eff_src['F'] + eff_src['G'] - eff_src['T']).abs() <= 1).sum())}"
         f" sur {len(eff_src)} à un élève près"),
        ("abandon_filles_garcons_pondere_egal_ensemble", bool((ecart_ab <= 1).mean() >= 0.95),
         f"moyenne des abandons F et G pondérée par les effectifs à 1 point de l'ensemble pour "
         f"{int((ecart_ab <= 1).sum())} passages sur {len(ecart_ab)} (écart médian {ecart_ab.median():.3f})"),
        ("statut_de_chaque_cellule", len(statut) == len(table) * len(PAR_SEXE),
         ", ".join(f"{k} {v}" for k, v in compte.items())),
        ("cibles_observees_par_sexe", int(table["cible_observee"].sum()) > 0,
         f"{int(table['cible_observee'].sum())} cibles observées (province × année × sexe)"),
    ]
    return pd.DataFrame(resultats, columns=["controle", "conforme", "detail"])


def executer(base: pd.DataFrame, statuts: pd.DataFrame, sortie) -> dict[str, pd.DataFrame]:
    sources = sources_par_sexe()
    table, statut = construire(base, statuts, sources)
    controles = controler(table, statut, base, sources)
    tables = {"base_apuree_par_sexe": table, "statut_cellules_par_sexe": statut,
              "controles_apurement_par_sexe": controles}
    for nom, t in tables.items():
        t.to_csv(sortie / f"{nom}.csv", sep=config.SEPARATEUR, encoding=config.ENCODAGE_SORTIE, index=False)
    return tables
