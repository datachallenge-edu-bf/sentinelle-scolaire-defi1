"""Analyse exploratoire avant la modélisation : la cible, sa variance, la qualité des variables,
leur colinéarité et leur lien avec la cible, puis une décision motivée pour chaque variable.

Deux bases sont analysées : l'ensemble des élèves (base apurée) et la base par sexe.

La cible de l'année t est l'abandon du primaire entre t et t+1, c'est-à-dire la valeur
``abandon_primaire_precedent`` de l'année t+1 pour la même province (et le même sexe). Seules
les cibles observées sont analysées.

Règle contre la fuite d'information : les analyses qui n'utilisent pas la cible (qualité,
colinéarité) portent sur toutes les années ; celles qui l'utilisent (variance, liens) portent
sur les années d'apprentissage seulement, avant l'année gardée pour le test final.

Ruptures de scolarisation : quand les effectifs du primaire de la province varient de plus de
30 % entre t et t+1 (règle de l'étape 03), l'abandon apparent mesure surtout la fermeture
d'écoles et le départ d'élèves, pas le décrochage. Ces lignes (8 % des cibles, 73 % de leur
variance) sont écartées des analyses de la cible et de l'apprentissage du modèle du décrochage ;
elles servent à l'alerte de rupture.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import spearmanr
from sklearn.feature_selection import mutual_info_regression

from ..apurement import par_sexe, selection
from ..apurement.etat import OBSERVEE

CIBLE = "abandon_primaire_precedent"
SUIVANTE = "cible"
# Année t des variables du test final : la dernière dont la cible (t+1) est observée.
ANNEE_TEST = {"ensemble": "2023-2024", "sexe": "2022-2023"}
SEUIL_CORRELATION = 0.85
SEUIL_VIF = 10.0
SEUIL_OBSERVEE = 0.5
SEUIL_RUPTURE = 0.30
# Lien faible et instable : |ρ global| et |ρ sachant l'abandon de t| au plus 0,10, même signe moins de 70 % des années.
SEUIL_LIEN_FAIBLE = 0.10
SEUIL_STABILITE = 0.70
# Variables retirées par le VIF mais rendues aux modèles d'arbres, que la colinéarité ne gêne pas.
SEUIL_RETOUR_ARBRES = 0.15
SEUIL_OBSERVEE_ARBRES = 0.75
GRAINE = 42

TECHNIQUES = {
    "cible_observee": "indicateur de travail (cible observée ou non)",
    "methode_population": "indicateur de travail (méthode de la population)",
    "abandon_primaire_precedent_province_origine": "valeur de la province d'origine, réservée aux provinces scindées",
    "redoublement_primaire_precedent_province_origine": "valeur de la province d'origine, réservée aux provinces scindées",
}
IDENTITES = {
    "promotion_primaire_precedente": "identité comptable : 100 − abandon − redoublement",
    "choc_eleves_primaire": "seuil de evolution_eleves_primaire (|évolution| > 30 %) : même information",
}
# Toujours gardée : l'abandon de l'année t, premier prédicteur attendu.
PRIORITAIRES = [CIBLE]


# Table d'apprentissage.

def annee_plus(annee: str, ecart: int) -> str:
    debut = int(annee[:4]) + ecart
    return f"{debut}-{debut + 1}"


def table_apprentissage(base: pd.DataFrame, statut_cible: pd.Series, entite: list[str],
                        evolution: pd.Series) -> pd.DataFrame:
    """Variables de l'année t et cible (abandon de t à t+1), avec son statut et la rupture éventuelle.

    ``evolution`` : évolution des effectifs du primaire (ensemble) par (province_pcode, année).
    """
    d = base.sort_values(entite + ["annee_scolaire"]).reset_index(drop=True)
    d[SUIVANTE] = d.groupby(entite)[CIBLE].shift(-1)
    suivante = d.groupby(entite)["annee_scolaire"].shift(-1)
    cles = list(zip(*(d[c] for c in entite), suivante))
    d["cible_statut"] = [statut_cible.get(k) for k in cles]
    d["cible_observee_suivante"] = d["cible_statut"] == OBSERVEE
    d["evolution_effectifs_suivante"] = [evolution.get((p, annee_plus(a, 1)), np.nan)
                                         for p, a in zip(d["province_pcode"], d["annee_scolaire"])]
    d["rupture"] = d["evolution_effectifs_suivante"].abs() > SEUIL_RUPTURE
    return d[d[SUIVANTE].notna()].reset_index(drop=True)


def charger(dossier) -> dict[str, dict]:
    """Tables d'apprentissage, variables candidates et statuts pour l'ensemble et par sexe."""
    lire = lambda nom: pd.read_csv(dossier / f"{nom}.csv", sep=";", encoding="utf-8-sig")  # noqa: E731
    base, statuts = lire("base_apuree"), lire("statut_cellules")
    base_sexe, statuts_sexe = lire("base_apuree_par_sexe"), lire("statut_cellules_par_sexe")

    st = statuts.set_index(["province_pcode", "annee_scolaire", "variable"])["statut"]
    st_sexe = statuts_sexe.set_index(["province_pcode", "sexe", "annee_scolaire", "variable"])["statut"]
    cible = st.xs(CIBLE, level="variable")
    cible_sexe = st_sexe.xs(CIBLE, level="variable")

    candidates = [c for c in selection.VARIABLES if c not in TECHNIQUES]
    communes = [c for c in base_sexe.columns if c in candidates and c not in par_sexe.PAR_SEXE]
    candidates_sexe = [c for c in par_sexe.PAR_SEXE + communes if c not in TECHNIQUES] + ["fille"]
    base_sexe["fille"] = (base_sexe["sexe"] == "F").astype(float)

    def part_observee(table, variables, avec_sexe):
        parts = {}
        for v in variables:
            if v == "fille":
                parts[v] = 1.0
            elif avec_sexe and v in par_sexe.PAR_SEXE:
                parts[v] = float((statuts_sexe.loc[statuts_sexe["variable"] == v, "statut"] == OBSERVEE).mean())
            else:
                parts[v] = float((statuts.loc[statuts["variable"] == v, "statut"] == OBSERVEE).mean())
        return pd.Series(parts)

    evolution = base.set_index(["province_pcode", "annee_scolaire"])["evolution_eleves_primaire"]
    return {
        "ensemble": {"base": base, "variables": candidates, "entite": ["province_pcode"],
                     "table": table_apprentissage(base, cible, ["province_pcode"], evolution),
                     "part_observee": part_observee(base, candidates, False), "statuts": statuts},
        "sexe": {"base": base_sexe, "variables": candidates_sexe, "entite": ["province_pcode", "sexe"],
                 "table": table_apprentissage(base_sexe, cible_sexe, ["province_pcode", "sexe"], evolution),
                 "part_observee": part_observee(base_sexe, candidates_sexe, True), "statuts": statuts,
                 "statuts_sexe": statuts_sexe},
    }


def numerique(table: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    return table[variables].apply(lambda s: s.astype(float))


def apprentissage(jeu: dict, nom: str, avec_ruptures: bool = False) -> pd.DataFrame:
    t = jeu["table"]
    garde = t["cible_observee_suivante"] & (t["annee_scolaire"] < ANNEE_TEST[nom])
    if not avec_ruptures:
        garde &= ~t["rupture"]
    return t[garde].reset_index(drop=True)


# 1. La cible.

def decrire_cible(table: pd.DataFrame, par: list[str]) -> pd.DataFrame:
    obs = table[table["cible_observee_suivante"]]
    g = obs.groupby(par)[SUIVANTE]
    return pd.DataFrame({
        "cibles_observees": g.size(), "ruptures": obs.groupby(par)["rupture"].sum(),
        "moyenne_hors_ruptures": obs[~obs["rupture"]].groupby(par)[SUIVANTE].mean(),
        "moyenne": g.mean(), "mediane": g.median(),
        "p10": g.quantile(0.1), "p90": g.quantile(0.9), "minimum": g.min(), "maximum": g.max(),
        "negatives": g.apply(lambda s: int((s < 0).sum())), "superieures_a_30": g.apply(lambda s: int((s > 30).sum())),
    }).round(2).reset_index()


# 2. Variance et persistance.

def decomposer_variance(app: pd.DataFrame, entite: list[str]) -> pd.DataFrame:
    y = app[SUIVANTE]
    moyenne_entite = app.groupby(entite)[SUIVANTE].transform("mean")
    entre, intra = float(moyenne_entite.var()), float((y - moyenne_entite).var())
    persistance = spearmanr(app[CIBLE], y).statistic
    # Références de prévision, calculées avec le seul passé.
    passe = app.sort_values(entite + ["annee_scolaire"]).groupby(entite)[CIBLE].transform(
        lambda s: s.expanding().mean())
    lignes = [
        ("variance_totale", y.var(), "variance de la cible (points²)"),
        ("variance_entre_provinces", entre, "variance des moyennes par province"),
        ("variance_dans_le_temps", intra, "variance des écarts à la moyenne de la province"),
        ("part_entre_provinces", entre / (entre + intra), "part de la variance due aux écarts entre provinces"),
        ("persistance_spearman", persistance, "corrélation de rang entre l'abandon de t et celui de t+1"),
        ("erreur_reference_annee_precedente", (y - app[CIBLE]).abs().mean(),
         "erreur absolue moyenne (points) si l'on prédit l'abandon de t"),
        ("erreur_reference_moyenne_passee", (y - passe.reindex(app.index)).abs().mean(),
         "erreur absolue moyenne si l'on prédit la moyenne des abandons passés de la province"),
        ("erreur_reference_mediane_annee", (y - app.groupby("annee_scolaire")[CIBLE].transform("median")).abs().mean(),
         "erreur absolue moyenne si l'on prédit la médiane des provinces de l'année t"),
    ]
    return pd.DataFrame(lignes, columns=["mesure", "valeur", "definition"]).round({"valeur": 4})


# 3. Qualité.

def qualite(base: pd.DataFrame, variables: list[str], entite: list[str], part_observee: pd.Series) -> pd.DataFrame:
    x = numerique(base, variables)
    intra = x.groupby([base[c] for c in entite]).std().max()
    return pd.DataFrame({
        "part_observee": part_observee.reindex(variables).round(3),
        "valeurs_distinctes": x.nunique(),
        "constante_dans_le_temps": intra.reindex(variables).fillna(0) < 1e-9,
        "coefficient_variation": (x.std() / x.mean().abs().replace(0, np.nan)).round(3),
    }).rename_axis("variable").reset_index()


# 4. Colinéarité.

def correlations(base: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    return numerique(base, variables).corr(method="spearman")


def groupes_colineaires(rho: pd.DataFrame, seuil: float = SEUIL_CORRELATION) -> pd.Series:
    """Groupes où toutes les paires ont |ρ| ≥ seuil (classification hiérarchique, lien complet)."""
    distance = (1 - rho.abs()).clip(lower=0).fillna(1).to_numpy(copy=True)
    np.fill_diagonal(distance, 0)
    arbre = linkage(squareform(distance, checks=False), method="complete")
    return pd.Series(fcluster(arbre, t=1 - seuil, criterion="distance"), index=rho.index, name="groupe")


def vif(x: pd.DataFrame) -> pd.Series:
    """Facteur d'inflation de la variance : diagonale de l'inverse de la matrice de corrélation."""
    r = x.corr().fillna(0).values
    return pd.Series(np.diag(np.linalg.pinv(r)), index=x.columns)


# 5. Lien avec la cible (années d'apprentissage).

def _rangs_residuels(y: np.ndarray, z: np.ndarray) -> np.ndarray:
    ry, rz = pd.Series(y).rank().values, pd.Series(z).rank().values
    pente = np.polyfit(rz, ry, 1)
    return ry - np.polyval(pente, rz)


def liens(app: pd.DataFrame, variables: list[str], entite: list[str]) -> pd.DataFrame:
    x, y = numerique(app, variables), app[SUIVANTE].astype(float)
    groupes = [app[c] for c in entite]
    x_moy, y_moy = x.groupby(groupes).transform("mean"), y.groupby(groupes).transform("mean")
    entre_x, entre_y = x.groupby(groupes).mean(), y.groupby(groupes).mean()
    lag = app[CIBLE].astype(float).values
    residu_y = _rangs_residuels(y.values, lag)
    info = mutual_info_regression(((x - x.mean()) / x.std().replace(0, 1)).fillna(0), y, random_state=GRAINE)
    lignes = []
    for j, v in enumerate(variables):
        xv = x[v]
        constante = xv.nunique() < 2
        par_annee = [] if constante else [spearmanr(s[v], y[s.index]).statistic
                                          for _, s in x.groupby(app["annee_scolaire"]) if s[v].nunique() > 1]
        rho = np.nan if constante else spearmanr(xv, y).statistic
        signe = np.sign(rho) if pd.notna(rho) else 0
        intra_x = xv - x_moy[v]
        lignes.append({
            "variable": v,
            "rho_global": rho,
            "p_valeur": np.nan if constante else spearmanr(xv, y).pvalue,
            "rho_entre_provinces": np.nan if entre_x[v].nunique() < 2 else spearmanr(entre_x[v], entre_y).statistic,
            "rho_dans_le_temps": np.nan if intra_x.abs().max() < 1e-12 else spearmanr(intra_x, y - y_moy).statistic,
            "rho_partiel_sachant_abandon_t": np.nan if (constante or v == CIBLE) else
            spearmanr(_rangs_residuels(xv.values, lag), residu_y).statistic,
            "information_mutuelle": info[j],
            "annees_meme_signe": np.nan if not par_annee else float(np.mean([np.sign(r) == signe for r in par_annee])),
        })
    return pd.DataFrame(lignes).round(4)


# 6. Décision.

def decider(variables: list[str], qual: pd.DataFrame, rho: pd.DataFrame, lien: pd.DataFrame,
            base: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    q = qual.set_index("variable")
    l = lien.set_index("variable")
    decision, motif = {}, {}
    for v in variables:
        if v in IDENTITES:
            decision[v], motif[v] = "retirée", f"redondante par construction : {IDENTITES[v]}"
        elif q.at[v, "valeurs_distinctes"] < 2:
            decision[v], motif[v] = "retirée", "constante : aucune information"
        elif q.at[v, "part_observee"] < SEUIL_OBSERVEE and v not in PRIORITAIRES:
            decision[v], motif[v] = "retirée", f"trop estimée : {q.at[v, 'part_observee']:.0%} de valeurs observées"
    restantes = [v for v in variables if v not in decision]

    # Colinéarité : un représentant par groupe.
    groupes = groupes_colineaires(rho.loc[restantes, restantes])
    def score(v):
        return (v in PRIORITAIRES, round(q.at[v, "part_observee"], 1),
                abs(l.at[v, "rho_global"]) if pd.notna(l.at[v, "rho_global"]) else 0)
    for g, membres in groupes.groupby(groupes):
        membres = list(membres.index)
        if len(membres) < 2:
            continue
        garde = max(membres, key=score)
        for v in membres:
            if v != garde:
                decision[v] = "retirée"
                motif[v] = (f"colinéaire avec {garde} (ρ = {rho.at[v, garde]:+.2f}), gardée car "
                            f"{'prioritaire' if garde in PRIORITAIRES else 'plus observée ou plus liée à la cible'}")
    restantes = [v for v in restantes if v not in decision]

    # Facteur d'inflation de la variance : tant qu'une variable dépasse le seuil, on retire, parmi celles
    # qui le dépassent, la moins liée à la cible ; l'information qu'elle porte reste dans les autres.
    x = numerique(base, restantes)
    force = lambda v: abs(l.at[v, "rho_global"]) if pd.notna(l.at[v, "rho_global"]) else 0  # noqa: E731
    while True:
        f = vif(x[restantes]).drop(PRIORITAIRES, errors="ignore")
        au_dessus = f[f > SEUIL_VIF]
        if au_dessus.empty:
            break
        v = min(au_dessus.index, key=force)
        decision[v], motif[v] = "retirée", (f"VIF = {au_dessus[v]:.1f} > {SEUIL_VIF:.0f} : combinaison linéaire des "
                                            f"autres variables, la moins liée à la cible parmi celles au-dessus du seuil")
        restantes.remove(v)
    # Membres d'un groupe dont le représentant a été retiré par le VIF.
    for v, m in list(motif.items()):
        if m.startswith("colinéaire avec "):
            garde = m.split(" ")[2]
            if decision.get(garde) == "retirée":
                motif[v] = m + " ; celle-ci est ensuite retirée par le VIF : l'information reste dans les autres variables"
    # Lien à la fois faible et instable : la variable n'apporte que du bruit.
    for v in list(restantes):
        if v in PRIORITAIRES:
            continue
        partiel = l.at[v, "rho_partiel_sachant_abandon_t"]
        faible = abs(l.at[v, "rho_global"]) <= SEUIL_LIEN_FAIBLE and (pd.isna(partiel) or abs(partiel) <= SEUIL_LIEN_FAIBLE)
        instable = pd.notna(l.at[v, "annees_meme_signe"]) and l.at[v, "annees_meme_signe"] < SEUIL_STABILITE
        if faible and instable:
            decision[v] = "retirée"
            motif[v] = (f"lien faible et instable : ρ = {l.at[v, 'rho_global']:+.2f}, même signe "
                        f"{l.at[v, 'annees_meme_signe']:.0%} des années")
            restantes.remove(v)
    f_final = vif(x[restantes])
    for v in restantes:
        decision[v], motif[v] = "gardée", "candidate pour le modèle"
    table = (pd.DataFrame({"variable": variables, "decision": [decision[v] for v in variables],
                           "motif": [motif[v] for v in variables]})
             .merge(qual, on="variable", how="left").merge(lien, on="variable", how="left"))
    table["groupe_colineaire"] = table["variable"].map(groupes)
    table["vif_final"] = table["variable"].map(f_final.round(2))
    # Deux listes : modèles linéaires (après VIF) ; modèles d'arbres (variables retirées par le seul VIF
    # rendues si elles sont nettement liées à la cible et assez observées).
    table["liste_lineaire"] = table["decision"] == "gardée"
    retour = (table["motif"].str.startswith("VIF") & (table["rho_global"].abs() >= SEUIL_RETOUR_ARBRES)
              & (table["part_observee"] >= SEUIL_OBSERVEE_ARBRES))
    table["liste_arbres"] = table["liste_lineaire"] | retour
    ordre = {"gardée": 0, "retirée": 1}
    table = table.sort_values(["decision", "rho_global"], key=lambda s: s.map(ordre) if s.name == "decision"
                              else -s.abs()).reset_index(drop=True)
    composition = (groupes.rename_axis("variable").reset_index()
                   .assign(taille=lambda d: d.groupby("groupe")["variable"].transform("size")))
    composition = composition[composition["taille"] > 1].sort_values(["groupe", "variable"])
    return table, composition


def analyser(jeu: dict, nom: str) -> dict[str, pd.DataFrame]:
    variables, entite, base = jeu["variables"], jeu["entite"], jeu["base"]
    app = apprentissage(jeu, nom)
    par = ["annee_scolaire"] + (["sexe"] if nom == "sexe" else [])
    qual = qualite(base, variables, entite, jeu["part_observee"])
    rho = correlations(base, variables)
    lien = liens(app, variables, entite)
    decision, groupes = decider(variables, qual, rho, lien, base)
    techniques = pd.DataFrame([{"variable": v, "decision": "retirée", "motif": f"technique : {m}",
                                "liste_lineaire": False, "liste_arbres": False}
                               for v, m in TECHNIQUES.items() if v in base])
    decision = pd.concat([decision, techniques], ignore_index=True)
    variance = decomposer_variance(app, entite).rename(columns={"valeur": "sans_ruptures"})
    variance.insert(1, "avec_ruptures", decomposer_variance(apprentissage(jeu, nom, True), entite)["valeur"])
    t = jeu["table"]
    ruptures = t[t["cible_observee_suivante"] & t["rupture"]][
        ["province_nom", "region_nom", "annee_scolaire"] + (["sexe"] if nom == "sexe" else [])
        + [SUIVANTE, CIBLE, "evolution_effectifs_suivante"]].round(3)
    listes = decision[decision["liste_arbres"]][["variable", "liste_lineaire", "liste_arbres", "rho_global",
                                                  "part_observee"]].reset_index(drop=True)
    return {f"cible_par_annee_{nom}": decrire_cible(jeu["table"], par),
            f"variance_cible_{nom}": variance,
            f"ruptures_{nom}": ruptures,
            f"variables_modele_{nom}": listes,
            f"correlations_{nom}": rho.round(4).rename_axis("variable").reset_index(),
            f"groupes_colineaires_{nom}": groupes,
            f"decision_variables_{nom}": decision}
