"""Étape 1 : recodage des valeurs impossibles et imputation variable par variable.

Recodage en manquant :

- valeurs infinies (division par zéro à la source) ;
- taux de flux calculés sur une province sans élève (Komandjari 2022-2023) ;
- taux d'abandon, de redoublement ou de promotion hors de [-5 ; 105] % (les trois taux de la ligne) ;
- réussite au CEP supérieure à 105 %.

Imputation, pour chaque variable et chaque province (hors provinces scindées) :

- la part de manquants décide de ce qui est imputé : jusqu'à 40 %, tout ; de 40 à 50 %, les
  trous intérieurs ; au-delà de 50 %, rien ;
- chaque cellule vide est classée début de série, fin de série ou trou intérieur ;
- pour chaque type, des valeurs connues de même nature sont masquées puis estimées par chaque
  méthode candidate (report de l'année voisine, interpolation, moyenne ou médiane de la province,
  tendance locale) ; la méthode à la plus faible erreur est retenue ;
- un trou partiel la dernière année (au moins 5 provinces) est aussi testé par régression et
  plus proches voisins sur les années précédentes ;
- la valeur imputée est bornée à la plage observée de la variable et arrondie comme elle.

Les provinces scindées reçoivent la médiane des provinces de leur ancienne région la même année ;
leurs effectifs sont reconstruits à l'étape 3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .etat import IMPUTEE, Apurement

QUALITATIVES = ["methode_population"]
LOGIQUES = ["choc_eleves_primaire", "cible_observee"]
FLUX = ["abandon_primaire_precedent", "redoublement_primaire_precedent", "promotion_primaire_precedente"]
ORIGINE = {"abandon_primaire_precedent_province_origine": "abandon_primaire_precedent",
           "redoublement_primaire_precedent_province_origine": "redoublement_primaire_precedent"}
FLUX_ET_ORIGINE = FLUX + list(ORIGINE)
EFFECTIFS = ["eleves_primaire", "evolution_eleves_primaire", "promotion_primaire_precedente", *ORIGINE]

INTERPOLATION = "interpolation linéaire"
REPORT_PRECEDENT = "report de l'année précédente"
REPORT_SUIVANT = "report de l'année suivante"
MOYENNE = "moyenne de la province"
MEDIANE = "médiane de la province"
TENDANCE = "tendance linéaire locale"
REGRESSION = "régression linéaire (y(t) sur y(t-1))"
VOISINS = "KNN (k=3, y(t-1) et y(t-2))"
PREFERENCE = [INTERPOLATION, REPORT_PRECEDENT, REPORT_SUIVANT, MEDIANE, MOYENNE, TENDANCE]
AUTORISEES = {"interieur": ("interp", "precedent", "moyenne", "mediane"),
              "debut": ("suivant", "moyenne", "mediane", "tendance"),
              "fin": ("precedent", "moyenne", "mediane", "tendance")}
LIBELLE_TYPE = {"debut": "début de série", "fin": "fin de série", "interieur": "trou intérieur"}


def candidats(s: np.ndarray, t: int, autorisees: tuple[str, ...]) -> dict[str, float]:
    """Valeur de chaque méthode candidate pour la cellule t de la série s (NaN = absent)."""
    obs = np.where(~np.isnan(s))[0]
    sortie = {}
    if len(obs) == 0:
        return sortie
    avant, apres = obs[obs < t], obs[obs > t]
    if "interp" in autorisees and len(avant) and len(apres):
        a, b = avant[-1], apres[0]
        sortie[INTERPOLATION] = s[a] + (s[b] - s[a]) * (t - a) / (b - a)
    if "precedent" in autorisees and len(avant):
        sortie[REPORT_PRECEDENT] = s[avant[-1]]
    if "suivant" in autorisees and len(apres):
        sortie[REPORT_SUIVANT] = s[apres[0]]
    if "moyenne" in autorisees:
        sortie[MOYENNE] = float(np.nanmean(s))
    if "mediane" in autorisees:
        sortie[MEDIANE] = float(np.nanmedian(s))
    if "tendance" in autorisees and len(obs) >= 3:
        proches = obs[np.argsort(abs(obs - t))[:4]]
        sortie[TENDANCE] = float(np.polyval(np.polyfit(proches, s[proches], 1), t))
    return sortie


def type_de_trou(s: np.ndarray, t: int) -> str:
    obs = np.where(~np.isnan(s))[0]
    if len(obs) == 0:
        return "vide"
    if t < obs[0]:
        return "debut"
    if t > obs[-1]:
        return "fin"
    return "interieur"


def tester(matrice: pd.DataFrame, type_trou: str, longueur: int) -> dict[str, float]:
    """Erreur absolue moyenne de chaque méthode sur des valeurs connues masquées du même type."""
    erreurs: dict[str, list[float]] = {}
    for _, rang in matrice.iterrows():
        s = rang.to_numpy(dtype=float)
        obs = np.where(~np.isnan(s))[0]
        if type_trou == "interieur":
            for t in obs[1:-1]:
                masquee = s.copy()
                masquee[t] = np.nan
                for m, v in candidats(masquee, t, AUTORISEES["interieur"]).items():
                    erreurs.setdefault(m, []).append(abs(v - s[t]))
        else:
            if len(obs) < longueur + 3:
                continue
            caches = obs[:longueur] if type_trou == "debut" else obs[-longueur:]
            masquee = s.copy()
            masquee[caches] = np.nan
            for t in caches:
                for m, v in candidats(masquee, t, AUTORISEES[type_trou]).items():
                    erreurs.setdefault(m, []).append(abs(v - s[t]))
    return {m: float(np.mean(e)) for m, e in erreurs.items() if e}


def _prevision_transversale(matrice: pd.DataFrame, t: int, apprentissage: np.ndarray, cibles: np.ndarray,
                            methode: str) -> np.ndarray:
    """Valeur de l'année t à partir des années t-1 (et t-2) des autres provinces."""
    x1, x2, y = matrice[t - 1].to_numpy(), matrice[t - 2].to_numpy(), matrice[t].to_numpy()
    if methode == REGRESSION:
        a = np.c_[np.ones(len(apprentissage)), x1[apprentissage]]
        coef = np.linalg.lstsq(a, y[apprentissage], rcond=None)[0]
        return coef[0] + coef[1] * x1[cibles]
    if methode == VOISINS:
        x = np.c_[x1, x2]
        mu, sd = np.nanmean(x[apprentissage], 0), np.nanstd(x[apprentissage], 0) + 1e-9
        z = (x - mu) / sd
        sortie = []
        for j in cibles:
            distances = np.sqrt(((z[apprentissage] - z[j]) ** 2).sum(1))
            sortie.append(y[apprentissage[np.argsort(distances)[:3]]].mean())
        return np.array(sortie)
    if methode == REPORT_PRECEDENT:
        return x1[cibles]
    if methode == MEDIANE:
        return np.array([np.nanmedian(matrice.to_numpy()[j]) for j in cibles])
    raise ValueError(methode)


def tester_derniere_annee(matrice: pd.DataFrame, manquants: int, rng: np.random.Generator) -> dict[str, float]:
    """Trou partiel la dernière année : on masque l'avant-dernière année, 60 tirages de provinces."""
    derniere = matrice.columns[-1]
    t = derniere - 1
    completes = np.where(matrice[derniere - 1].notna().to_numpy() & matrice[derniere - 2].notna().to_numpy())[0]
    methodes = [REPORT_PRECEDENT, MEDIANE, REGRESSION, VOISINS]
    erreurs = {m: [] for m in methodes}
    valeurs = matrice.to_numpy()
    for _ in range(60):
        cibles = rng.choice(completes, size=min(manquants, len(completes) - 3), replace=False)
        apprentissage = np.setdiff1d(completes, cibles)
        verite = matrice[t].to_numpy()[cibles]
        for m in methodes:
            if m == MEDIANE:
                prevision = np.array([np.nanmedian(np.r_[valeurs[j][:t], valeurs[j][t + 1:]]) for j in cibles])
            else:
                prevision = _prevision_transversale(matrice, t, apprentissage, cibles, m)
            erreurs[m].append(np.mean(np.abs(prevision - verite)))
    return {m: float(np.mean(e)) for m, e in erreurs.items()}


def _choisir(erreurs: dict[str, float], preference: list[str]) -> tuple[str | None, float | None]:
    if not erreurs:
        return None, None
    rang = lambda m: (round(erreurs[m], 10), preference.index(m) if m in preference else 99)  # noqa: E731
    meilleure = min(erreurs, key=rang)
    return meilleure, erreurs[meilleure]


def _decimales(valeurs: np.ndarray) -> int:
    return int(min(4, max(len(str(v).split(".")[-1]) if "." in str(v) else 0 for v in valeurs[:300])))


class Etape1:
    """Recodage puis imputation ; garde le profil des manquants et les tests pour le rapport."""

    def __init__(self, etat: Apurement):
        self.etat = etat
        self.rapport: dict[str, dict] = {}
        self.tests_derniere_annee: dict[str, dict] = {}
        self.sans_objet: set[tuple[int, str]] = set()
        self.annees = sorted(etat.base["annee_scolaire"].unique())

    # Recodage.
    def recoder(self) -> None:
        d, e = self.etat.base, self.etat
        variables = [c for c in d.columns[10:] if c not in QUALITATIVES + LOGIQUES]
        self.numeriques = variables
        for c in variables:
            d[c] = pd.to_numeric(d[c], errors="coerce").astype(float)
            for i in d.index[np.isinf(d[c])]:
                e.noter(1, i, c, "inf", np.nan, "valeur infinie recodée en manquant", "division par zéro à la source",
                        nature="recodage")
                self.sans_objet.add((i, c))
            d.loc[np.isinf(d[c]), c] = np.nan
        for c in LOGIQUES:
            d[c] = d[c].map({True: True, False: False, "True": True, "False": False, "TRUE": True, "FALSE": False}).astype(object)
        scindee = e.scindee
        sans_eleve = d.index[(d["eleves_primaire"] == 0) & ~scindee]
        for i in sans_eleve:
            self.sans_objet.update((i, c) for c in d.columns[10:] if c != "eleves_primaire")
            for c in FLUX_ET_ORIGINE:
                if not np.isnan(d.at[i, c]):
                    e.noter(1, i, c, float(d.at[i, c]), np.nan, "valeur sans objet recodée en manquant",
                            "taux calculé sur une base de 0 élève", nature="recodage")
                    d.at[i, c] = np.nan
        for i in d.index[~scindee]:
            taux = [d.at[i, c] for c in FLUX]
            if any(not np.isnan(x) and (x < -5 or x > 105) for x in taux) and (i, FLUX[0]) not in self.sans_objet:
                for c in FLUX_ET_ORIGINE:
                    if not np.isnan(d.at[i, c]):
                        e.noter(1, i, c, float(d.at[i, c]), np.nan, "valeur aberrante recodée en manquant",
                                "taux d'abandon, de redoublement ou de promotion hors de [-5 ; 105] %", nature="recodage")
                        d.at[i, c] = np.nan
        for i in d.index[d["reussite_cep_precedente_province"] > 105]:
            e.noter(1, i, "reussite_cep_precedente_province", float(d.at[i, "reussite_cep_precedente_province"]),
                    np.nan, "valeur aberrante recodée en manquant", "taux de réussite supérieur à 105 %", nature="recodage")
            d.at[i, "reussite_cep_precedente_province"] = np.nan
        self.avant = d.copy()
        self.sans_objet_par_variable = pd.Series(
            {c: sum(1 for (i, v) in self.sans_objet if v == c and pd.isna(d.at[i, c])) for c in d.columns[10:]})

    # Profil des manquants.
    def _profil(self) -> pd.DataFrame:
        d, scindee = self.etat.base, self.etat.scindee
        lignes = [(c, int(d[c].isna().sum()), int(d.loc[~scindee, c].isna().sum()))
                  for c in self.numeriques + QUALITATIVES + LOGIQUES]
        profil = pd.DataFrame(lignes, columns=["variable", "manquants", "manquants_hors_scindees"]).set_index("variable")
        profil["part"] = profil["manquants"] / len(d)
        profil["part_hors_scindees"] = profil["manquants_hors_scindees"] / int((~scindee).sum())
        return profil

    def _matrice(self, c: str) -> pd.DataFrame:
        d = self.etat.base
        sous = d.loc[~self.etat.scindee].assign(_t=lambda x: x["annee_scolaire"].map(self.annees.index))
        return sous.pivot(index="province_pcode", columns="_t", values=c).reindex(columns=range(len(self.annees)))

    def _ligne(self, pcode: str, t: int) -> int:
        d = self.etat.base
        return d.index[(d["province_pcode"] == pcode) & (d["annee_scolaire"] == self.annees[t])][0]

    def imputer(self, rng: np.random.Generator) -> None:
        d, e = self.etat.base, self.etat
        self.profil = profil = self._profil()
        # Trous à combler, par variable et par type, et tests des méthodes.
        trous: dict[str, tuple] = {}
        for c in self.numeriques:
            if c in ORIGINE or c == "promotion_primaire_precedente" or profil.loc[c, "manquants_hors_scindees"] == 0:
                continue
            m = self._matrice(c)
            par_type: dict[str, list] = {}
            for pcode, rang in m.iterrows():
                s = rang.to_numpy(dtype=float)
                for t in np.where(np.isnan(s))[0]:
                    if (self._ligne(pcode, t), c) in self.sans_objet:
                        continue
                    par_type.setdefault(type_de_trou(s, t), []).append((pcode, t))
            tests = {}
            for type_trou, cellules in par_type.items():
                if type_trou == "vide":
                    continue
                longueur = 1
                if type_trou in ("debut", "fin"):
                    longueur = max(sum(1 for p, _ in cellules if p == q) for q in {p for p, _ in cellules})
                tests[type_trou] = {"n": len(cellules), "longueur": longueur, "erreurs": tester(m, type_trou, longueur)}
            observees = m.to_numpy()[~np.isnan(m.to_numpy())]
            echelle = np.mean(np.abs(observees - np.median(observees)))
            trous[c] = (profil.loc[c, "part_hors_scindees"], par_type, tests, echelle if echelle > 0 else 1.0)
        for c in self.numeriques:
            if c in ORIGINE or profil.loc[c, "manquants_hors_scindees"] == 0:
                continue
            m = self._matrice(c)
            manquants = int(m[m.columns[-1]].isna().sum())
            if 5 <= manquants < len(m):
                self.tests_derniere_annee[c] = tester_derniere_annee(m, manquants, rng)
        # Imputation des provinces non scindées.
        for c, (part, par_type, tests, echelle) in trous.items():
            m = self._matrice(c)
            observees = m.to_numpy()[~np.isnan(m.to_numpy())]
            bas, haut = observees.min(), observees.max()
            if c in FLUX:
                bas, haut = max(bas, 0.0), min(haut, 100.0)
            decimales = _decimales(observees)
            resume = []
            for type_trou, cellules in par_type.items():
                if type_trou == "vide":
                    continue
                test = tests[type_trou]
                erreurs = dict(test["erreurs"])
                if type_trou == "fin" and c in self.tests_derniere_annee:
                    erreurs.update(self.tests_derniere_annee[c])
                methode, erreur = _choisir(erreurs, PREFERENCE + list(self.tests_derniere_annee.get(c, {})))
                permis = part <= 0.4 or (part <= 0.5 and type_trou == "interieur")
                resume.append({"type": type_trou, "n": test["n"], "longueur": test["longueur"], "methode": methode,
                               "erreur": None if erreur is None else erreur / echelle, "permis": permis,
                               "candidats": {k: round(v / echelle, 3) for k, v in erreurs.items()}})
                if not permis or methode is None:
                    continue
                for pcode, t in cellules:
                    i = self._ligne(pcode, t)
                    s = m.loc[pcode].to_numpy(dtype=float)
                    if type_trou == "fin" and methode in (REGRESSION, VOISINS):
                        apprentissage = np.where(m[t].notna().to_numpy() & m[t - 1].notna().to_numpy()
                                                 & m[t - 2].notna().to_numpy())[0]
                        cible = np.array([list(m.index).index(pcode)])
                        v = float(_prevision_transversale(m, t, apprentissage, cible, methode)[0])
                    else:
                        v = candidats(s, t, AUTORISEES[type_trou]).get(methode)
                        if v is None:
                            v = float(np.nanmedian(s))
                    v = round(float(np.clip(v, bas, haut)), decimales)
                    d.at[i, c] = v
                    e.noter(1, i, c, self.avant.at[i, c], v, methode,
                            f"{LIBELLE_TYPE[type_trou]} ; trou de {test['longueur']} an(s)")
            regle = ("aucune imputation (plus de 50 % de manquants hors provinces scindées)" if part > 0.5 else
                     "bords non imputés (40 à 50 % de manquants) : seuls les trous intérieurs sont comblés"
                     if part > 0.4 else "")
            self.rapport[c] = {"part": part, "types": resume, "regle": regle}
        # Colonnes « province d'origine » : identiques à leur variable de référence.
        scindee = e.scindee
        for colonne, reference in ORIGINE.items():
            for i in d.index[~scindee]:
                if np.isnan(d.at[i, colonne]) and not np.isnan(d.at[i, reference]):
                    d.at[i, colonne] = d.at[i, reference]
                    e.noter(1, i, colonne, self.avant.at[i, colonne], d.at[i, reference],
                            "copie de la variable de référence imputée",
                            f"identique à {reference} sur 100 % des lignes observées")
        # Provinces scindées : médiane de l'ancienne région la même année.
        annee = d["annee_scolaire"]
        for c in self.numeriques:
            if c in EFFECTIFS or not d.loc[scindee, c].isna().any():
                continue
            for i in d.index[scindee]:
                if not np.isnan(d.at[i, c]):
                    continue
                autres = d.loc[~scindee]
                voisines = autres[(autres["region_ancienne_nom"] == d.at[i, "region_ancienne_nom"])
                                  & (autres["annee_scolaire"] == annee[i])][c].dropna()
                methode = "médiane de l'ancienne région et de l'année"
                if voisines.empty:
                    voisines = autres[autres["annee_scolaire"] == annee[i]][c].dropna()
                    methode = "médiane nationale de l'année"
                if voisines.empty:
                    continue
                v = float(voisines.median())
                d.at[i, c] = v
                e.noter(1, i, c, "", round(v, 4), methode, "province scindée : ligne entièrement vide")
        # Promotion : identité comptable.
        for i in d.index:
            if (np.isnan(d.at[i, "promotion_primaire_precedente"]) and (i, "promotion_primaire_precedente")
                    not in self.sans_objet and not np.isnan(d.at[i, FLUX[0]]) and not np.isnan(d.at[i, FLUX[1]])):
                v = round(100 - d.at[i, FLUX[0]] - d.at[i, FLUX[1]], 2)
                d.at[i, "promotion_primaire_precedente"] = v
                e.noter(1, i, "promotion_primaire_precedente", self.avant.at[i, "promotion_primaire_precedente"], v,
                        "identité comptable (100 − abandon − redoublement)", "cohérence des trois taux")
        # Variables qualitative et logique.
        mode = d.loc[~scindee].groupby("annee_scolaire")["methode_population"].agg(lambda s: s.mode().iat[0])
        for i in d.index[d["methode_population"].isna()]:
            d.at[i, "methode_population"] = mode[d.at[i, "annee_scolaire"]]
            e.noter(1, i, "methode_population", "", d.at[i, "methode_population"], "mode de l'année",
                    "modalité unique de l'année sur les autres provinces")
        for i in d.index[d["cible_observee"].isna()]:
            d.at[i, "cible_observee"] = False
            e.noter(1, i, "cible_observee", "", "FALSE", "règle logique", "cible non observée pour une province scindée")
        # Statut des cellules et des lignes.
        comptes: dict[int, int] = {}
        for ligne in e.journal:
            if ligne["etape"] == 1 and ligne["nature"] == "imputation" and ligne["methode"] != "règle logique":
                e.statut[(ligne["_i"], ligne["variable"])] = IMPUTEE
                comptes[ligne["_i"]] = comptes.get(ligne["_i"], 0) + 1
        e.imputations_par_ligne = comptes
        e.statut_ligne = {i: "province scindée (valeurs de l'étape 03 complétées)" if scindee[i] else
                          ("partielle" if comptes.get(i, 0) else "aucune") for i in d.index}


def executer(etat: Apurement, graine: int = 42) -> Etape1:
    etape = Etape1(etat)
    etape.recoder()
    etape.imputer(np.random.default_rng(graine))
    return etape
