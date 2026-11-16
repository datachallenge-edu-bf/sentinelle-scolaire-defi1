"""Étape 3 : complétion des cellules encore vides.

Par ordre de préférence :

1. une donnée publiée ou observée : une valeur du panel n'est jamais remplacée ; pour les provinces
   scindées, les effectifs manquants viennent de la somme de leurs communes (annuaires régionaux
   de l'INSD lus à l'étape 02), et le TBS, l'achèvement et la parité du post-primaire manquants,
   de la province d'origine (Soum, Tapoa) publiés par l'INSD ;
2. une relation exacte vérifiée sur les lignes observées : promotion = 100 − abandon −
   redoublement ; écart d'achèvement = achèvement du primaire − TBA en 6e ; choc = |évolution| > 30 % ;
3. sinon une méthode choisie par test, sur des valeurs connues masquées (début, fin ou milieu de
   série) : report ou interpolation, moyenne, tendance, régression à effets fixes sur le TBS et
   l'achèvement du post-primaire, désormais complets.

Les valeurs restent dans la plage observée de la province (ou de la région) ; les variables
régionales sont estimées une fois par région et par année, puis recopiées sur ses provinces.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config
from .etat import COMPLETEE, SCINDEES, Apurement
from .imputation import ORIGINE

POST_PRIMAIRE = ["tba_6e_province", "abandon_post_primaire_province", "redoublement_3e_province",
                 "ratio_eleves_classe_post_primaire_region",
                 "part_etab_post_primaire_secondaire_publics_electricite_region",
                 "part_etab_post_primaire_secondaire_publics_cantine_region", "ecart_achevement_primaire_entree_6e"]
POST_PRIMAIRE_INSD = ["tbs_post_primaire_province", "achevement_post_primaire_province",
                      "parite_tbs_post_primaire_province"]
EFFECTIFS = ["eleves_primaire", "evolution_eleves_primaire", "choc_eleves_primaire"]
COVARIABLES = ["tbs_post_primaire_province", "achevement_post_primaire_province"]
BORNES = {"tba_6e_province": (0, 150), "abandon_post_primaire_province": (0, 100), "redoublement_3e_province": (0, 100),
          "ratio_eleves_classe_post_primaire_region": (0, None),
          "part_etab_post_primaire_secondaire_publics_electricite_region": (0, 1),
          "part_etab_post_primaire_secondaire_publics_cantine_region": (0, 1)}
ORIGINE_SCINDEE = {"Djelgodji": "Soum", "Karo-Peli": "Soum", "Dyamongou": "Tapoa", "Gobnangou": "Tapoa"}
ANNEES_INSD = [0, 1, 2, 6, 7]  # 2016-2017, 2017-2018, 2018-2019, 2022-2023, 2023-2024

VOISIN = "report/interpolation (voisin le plus proche)"
MOYENNE = "moyenne de l'unité"
TENDANCE = "tendance linéaire de l'unité"
REGRESSION = "régression à effets fixes (TBS et achèvement post-primaire sourcés)"


def effectifs_communaux() -> tuple[pd.Series, pd.Series]:
    """Élèves du primaire et enfants de 6 à 11 ans par province de 2025 et année, sommés sur les communes."""
    insd = pd.read_csv(config.SORTIE_NETTOYAGE / "fait_insd_commune.csv", sep=config.SEPARATEUR,
                       encoding=config.ENCODAGE_SORTIE)
    insd = insd[insd["indicateur"].isin(["eleves_par_sexe", "eleves_par_statut"]) & (insd["modalite"] == "T")]
    # Le tableau par sexe prime ; celui par statut complète ses manques.
    insd = insd.assign(rang=(insd["indicateur"] == "eleves_par_statut").astype(int)).sort_values("rang")
    insd = insd.drop_duplicates(["commune_pcode", "annee_scolaire"])
    communes = pd.read_csv(config.SORTIE_NETTOYAGE / "commune.csv", sep=config.SEPARATEUR,
                           encoding=config.ENCODAGE_SORTIE)[["commune_pcode", "province_nom"]]
    eleves = insd.merge(communes, on="commune_pcode").groupby(["province_nom", "annee_scolaire"])["valeur"].sum(
        min_count=1)
    panel = pd.read_csv(config.DONNEES / "03_transformation" / "panel_commune_annee.csv", sep=config.SEPARATEUR,
                        encoding=config.ENCODAGE_SORTIE)
    enfants = panel.groupby(["province_nom", "annee_scolaire"])["enfants_6_11"].sum(min_count=1)
    return eleves, enfants


def _large(table: pd.DataFrame, variable: str, unite: str, annees: list[str]) -> pd.DataFrame:
    return table.pivot_table(index=unite, columns="annee_scolaire", values=variable, aggfunc="mean").reindex(
        columns=annees)


def methodes(y: pd.DataFrame, covariables: dict[str, pd.DataFrame]) -> dict[str, np.ndarray]:
    """Prévision de chaque cellule de y (unités × années) par quatre méthodes."""
    a = y.to_numpy().copy()
    n = a.shape[1]
    sortie = {}
    voisin = np.full_like(a, np.nan)
    tendance = np.full_like(a, np.nan)
    for r in range(a.shape[0]):
        o = np.where(~np.isnan(a[r]))[0]
        if len(o):
            voisin[r] = np.interp(range(n), o, a[r, o])
        if len(o) >= 3:
            tendance[r] = np.polyval(np.polyfit(o, a[r, o], 1), range(n))
    sortie[VOISIN] = voisin
    with np.errstate(all="ignore"):
        sortie[MOYENNE] = np.tile(np.nanmean(a, axis=1)[:, None], (1, n))
    sortie[TENDANCE] = tendance
    # Régression à effets fixes : écarts à la moyenne de l'unité, sur les cellules observées.
    x = np.stack([c.to_numpy() for c in covariables.values()], axis=2)
    observe = ~np.isnan(a)
    with np.errstate(all="ignore"):
        ym = np.where(observe, a, np.nan)
        moyenne_y = np.nanmean(ym, axis=1, keepdims=True)
        xm = np.where(observe[:, :, None], x, np.nan)
        moyenne_x = np.nanmean(xm, axis=1, keepdims=True)
    yd, xd = (ym - moyenne_y)[observe], (xm - moyenne_x)[observe]
    if len(yd) > 10:
        coef = np.linalg.lstsq(np.c_[xd], yd, rcond=None)[0]
        sortie[REGRESSION] = moyenne_y + np.einsum("utk,k->ut", x - moyenne_x, coef)
    return sortie


class Etape3:
    def __init__(self, etat: Apurement, sources: pd.DataFrame):
        self.etat, self.sources = etat, sources
        self.d = etat.base
        self.annees = sorted(self.d["annee_scolaire"].unique())
        self.depart = self.d.copy()
        self.tests: dict[str, dict] = {}
        self.calage = np.nan

    def _poser(self, i: int, variable: str, valeur, methode: str, detail: str = "") -> None:
        self.etat.noter(3, i, variable, self.d.at[i, variable], valeur, methode, detail)
        self.d.at[i, variable] = valeur

    def _completer(self, i: int, variable: str, valeur, methode: str, detail: str = "") -> None:
        """Comme _poser, mais seulement si la cellule est vide : une valeur du panel n'est jamais remplacée."""
        if pd.isna(self.d.at[i, variable]):
            self._poser(i, variable, valeur, methode, detail)

    @property
    def scindee(self) -> pd.Series:
        return self.d["province_nom"].isin(SCINDEES)

    def _interpoler(self, i: int, variable: str) -> float:
        serie = self.d[self.d["province_nom"] == self.d.at[i, "province_nom"]].set_index("annee_scolaire")[variable]
        o = serie.dropna()
        rang = self.annees.index
        return float(np.interp(rang(self.d.at[i, "annee_scolaire"]), [rang(a) for a in o.index], o.to_numpy()))

    def trous_isoles(self) -> None:
        """Cellules isolées hors provinces scindées (Komandjari 2022-2023 et 2023-2024, écoles fermées)."""
        d = self.d
        exclues = POST_PRIMAIRE + POST_PRIMAIRE_INSD + EFFECTIFS + list(ORIGINE) + ["promotion_primaire_precedente"]
        for variable in [c for c in d.columns[10:] if c not in ("cible_observee", "methode_population")]:
            if variable in exclues:
                continue
            for i in d.index[d[variable].isna() & ~self.scindee]:
                self._poser(i, variable, round(self._interpoler(i, variable), 4), "interpolation linéaire",
                            "aucun élève (écoles fermées) : indicateur non défini ; valeur contrefactuelle entre "
                            "les années voisines")
        for i in d.index[d["promotion_primaire_precedente"].isna() & ~self.scindee]:
            valeur = round(100 - d.at[i, "abandon_primaire_precedent"] - d.at[i, "redoublement_primaire_precedent"], 4)
            self._poser(i, "promotion_primaire_precedente", valeur, "identité comptable", "100 − abandon − redoublement")
        for i in d.index[d["evolution_eleves_primaire"].isna() & ~self.scindee]:
            self._poser(i, "evolution_eleves_primaire", round(self._interpoler(i, "evolution_eleves_primaire"), 4),
                        "interpolation linéaire", "évolution relative à 0 élève non définie")

    def effectifs_scindees(self) -> None:
        """Élèves des provinces scindées : somme des communes, sinon TBS × enfants de 6 à 11 ans × calage."""
        d = self.d
        eleves, enfants = effectifs_communaux()
        enfants_table = enfants.rename("enfants_6_11").reset_index()
        jointes = d[~self.scindee].merge(enfants_table, on=["province_nom", "annee_scolaire"])
        observees = jointes[jointes["eleves_primaire"] > 0]
        self.calage = calage = float((observees["eleves_primaire"]
                                      / (observees["tbs_primaire_province"] / 100 * observees["enfants_6_11"])).median())
        annees = ["2015-2016"] + self.annees
        for province in SCINDEES:
            serie = {}
            for annee in annees[:-1]:
                communes = eleves.get((province, annee), np.nan)
                if province != "Karo-Peli" and pd.notna(communes):
                    serie[annee] = (float(communes), "somme des communes (annuaires régionaux INSD)")
                else:
                    tbs = d.at[self.etat.ligne(province, annee if annee in self.annees else self.annees[0]),
                               "tbs_primaire_province"]
                    serie[annee] = (round(tbs / 100 * float(enfants.get((province, annee), np.nan)) * calage, 0),
                                    f"identité TBS × enfants 6-11 × {calage:.3f} (calage médian sur les provinces observées)")
            tbs = {a: d.at[self.etat.ligne(province, a), "tbs_primaire_province"] for a in self.annees[-2:]}
            serie[self.annees[-1]] = (round(serie[self.annees[-2]][0] * tbs[self.annees[-1]] / tbs[self.annees[-2]], 0),
                                      "année absente des annuaires régionaux : effectifs 2023-2024 × (TBS 2024-2025 / "
                                      "TBS 2023-2024)")
            for k, annee in enumerate(annees[1:], start=1):
                i = self.etat.ligne(province, annee)
                valeur, detail = serie[annee]
                self._completer(i, "eleves_primaire", valeur,
                                "effectifs communes" if "communes" in detail else "identité TBS × enfants", detail)
                evolution = valeur / serie[annees[k - 1]][0] - 1
                self._completer(i, "evolution_eleves_primaire", round(evolution, 4), "calcul",
                                "variation relative annuelle des effectifs reconstitués")
                self._completer(i, "choc_eleves_primaire", float(abs(evolution) > 0.3), "règle logique",
                                "1 si |évolution| > 30 %")
        for province in ["Djelgodji", "Karo-Peli"]:
            i = self.etat.ligne(province, self.annees[0])
            voisines = d[(d["region_ancienne_nom"] == d.at[i, "region_ancienne_nom"])
                         & (d["annee_scolaire"] == self.annees[0]) & ~self.scindee]["evolution_eleves_primaire"].dropna()
            evolution = float(voisines.median())
            self._completer(i, "evolution_eleves_primaire", round(evolution, 4),
                            "médiane de l'ancienne région et de l'année",
                            "effectifs 2015-2016 indisponibles : variation médiane des provinces de l'ancienne région")
            self._completer(i, "choc_eleves_primaire", float(abs(evolution) > 0.3), "règle logique",
                            "1 si |évolution| > 30 %")

    def post_primaire_scindees(self) -> None:
        """TBS, achèvement et parité du post-primaire de la province d'origine, publiés par l'INSD."""
        s = self.sources.set_index(["province_annuaire", "annee_scolaire"])
        annees_insd = [self.annees[k] for k in ANNEES_INSD]
        for province, origine in ORIGINE_SCINDEE.items():
            publie = {"tbs_post_primaire_province": [s.at[(origine, a), "tbs_post_primaire_ensemble"] for a in annees_insd],
                      "achevement_post_primaire_province": [s.at[(origine, a), "achevement_post_primaire_ensemble"]
                                                            for a in annees_insd],
                      "parite_tbs_post_primaire_province": [s.at[(origine, a), "parite"] for a in annees_insd]}
            for variable, valeurs in publie.items():
                serie = list(np.interp(range(8), ANNEES_INSD, valeurs))
                serie.append(serie[-1])
                for k, annee in enumerate(self.annees):
                    methode = ("province d'origine (annuaire INSD), valeur publiée" if k in ANNEES_INSD else
                               "province d'origine, interpolation entre années publiées" if k < 8 else
                               "province d'origine, report de 2023-2024")
                    self._completer(self.etat.ligne(province, annee), variable, round(float(serie[k]), 4), methode,
                                    f"{province} est issue de {origine} : la valeur publiée de {origine} est reprise")

    def _borner(self, variable: str, valeurs, depart: pd.DataFrame):
        bas, haut = BORNES.get(variable, (0, None))
        if variable == "ratio_eleves_classe_post_primaire_region":
            haut = 1.5 * np.nanmax(depart[variable])
        return np.clip(valeurs, bas, haut)

    def _modeliser(self, variable: str, unite: str) -> dict[tuple[str, str], tuple[float, str, str]]:
        sous = self.d[~self.scindee]
        y = _large(sous, variable, unite, self.annees)
        x = {c: _large(sous, c, unite, self.annees) for c in COVARIABLES}
        a = y.to_numpy()
        observe = ~np.isnan(a)
        colonnes = [j for j in range(len(self.annees)) if observe[:, j].any()]
        scenarios = {"début": [[colonnes[0]], [colonnes[0], colonnes[1]]],
                     "fin": [[colonnes[-1]], [colonnes[-2], colonnes[-1]]],
                     "intérieur": [[colonnes[j] for j in range(1, len(colonnes) - 1)][:1]]}
        echelle = np.nanmean(np.abs(a - np.nanmean(a)))
        erreurs: dict[str, dict[str, list]] = {}
        for type_trou, masques in scenarios.items():
            for masque in masques:
                if not masque:
                    continue
                essai = y.copy()
                essai.iloc[:, masque] = np.nan
                if np.isnan(essai.to_numpy()).all(axis=1).any() or (~np.isnan(essai.to_numpy())).sum(axis=1).min() < 2:
                    continue
                try:
                    previsions = methodes(essai, x)
                except np.linalg.LinAlgError:
                    continue
                for nom, p in previsions.items():
                    with np.errstate(all="ignore"):
                        erreur = np.nanmean(np.abs(p[:, masque] - a[:, masque])) / echelle
                    erreurs.setdefault(type_trou, {}).setdefault(nom, []).append(erreur)
        meilleures = {}
        for type_trou, par_methode in erreurs.items():
            scores = {m: float(np.mean(e)) for m, e in par_methode.items() if not np.isnan(np.mean(e))}
            meilleures[type_trou] = (min(scores, key=scores.get), scores)
        self.tests[variable] = meilleures
        previsions = methodes(y, x)
        decisions = {}
        for r, u in enumerate(y.index):
            for j, annee in enumerate(self.annees):
                if not np.isnan(a[r, j]):
                    continue
                o = np.where(observe[r])[0]
                type_trou = "début" if j < o.min() else "fin" if j > o.max() else "intérieur"
                nom = meilleures.get(type_trou, meilleures.get("fin"))[0]
                valeur = float(np.clip(self._borner(variable, previsions[nom][r, j], self.depart),
                                       np.nanmin(a[r]), np.nanmax(a[r])))
                if np.isnan(valeur):
                    nom = VOISIN
                    valeur = float(self._borner(variable, previsions[VOISIN][r, j], self.depart))
                decisions[(u, annee)] = (valeur, nom, type_trou)
        return decisions

    def post_primaire(self) -> None:
        d = self.d
        for variable in POST_PRIMAIRE[:-1]:
            unite = "region_nom" if variable.endswith("_region") else "province_nom"
            for (u, annee), (valeur, nom, type_trou) in self._modeliser(variable, unite).items():
                lignes = d.index[(d[unite] == u) & (d["annee_scolaire"] == annee) & ~self.scindee & d[variable].isna()]
                scores = self.tests[variable].get(type_trou, (None, {}))[1]
                detail = f"cellule de type « {type_trou} de série » ; test : " + " ; ".join(
                    f"{m} {e:.2f}" for m, e in sorted(scores.items(), key=lambda t: t[1]))
                for i in lignes:
                    self._poser(i, variable, round(valeur, 4), nom, detail)
        for i in d.index[d["ecart_achevement_primaire_entree_6e"].isna() & ~self.scindee]:
            self._poser(i, "ecart_achevement_primaire_entree_6e",
                        round(d.at[i, "achevement_primaire_province"] - d.at[i, "tba_6e_province"], 4),
                        "identité (achèvement primaire − TBA 6e)", "relation vérifiée sur les lignes observées")
        for variable in POST_PRIMAIRE:
            for i in d.index[d[variable].isna() & self.scindee]:
                annee, region = d.at[i, "annee_scolaire"], d.at[i, "region_ancienne_nom"]
                voisines = d[(d["region_ancienne_nom"] == region) & (d["annee_scolaire"] == annee) & ~self.scindee][
                    variable].dropna()
                if voisines.empty:
                    voisines = d[(d["annee_scolaire"] == annee) & ~self.scindee][variable].dropna()
                self._poser(i, variable, round(float(voisines.median()), 4), "médiane de l'ancienne région et de l'année",
                            f"ancienne région {region}")
        for colonne, reference in ORIGINE.items():
            for i in d.index[d[colonne].isna()]:
                self._poser(i, colonne, d.at[i, reference], "copie de la variable de référence",
                            "colonne identique à la référence sur 100 % des lignes observées")

    def statuts(self) -> None:
        e = self.etat
        dernieres = {}
        for ligne in e.journal:
            if ligne["etape"] == 3:
                dernieres[(ligne["_i"], ligne["variable"])] = ligne
        par_ligne: dict[int, int] = {}
        for (i, variable) in dernieres:
            e.statut[(i, variable)] = COMPLETEE
            par_ligne[i] = par_ligne.get(i, 0) + 1
        for i, n in par_ligne.items():
            e.imputations_par_ligne[i] = e.imputations_par_ligne.get(i, 0) + n
            e.statut_ligne[i] = "complétée à l'étape 3"


def executer(etat: Apurement, sources: pd.DataFrame) -> Etape3:
    etape = Etape3(etat, sources)
    etape.trous_isoles()
    etape.effectifs_scindees()
    etape.post_primaire_scindees()
    etape.post_primaire()
    etape.statuts()
    return etape
