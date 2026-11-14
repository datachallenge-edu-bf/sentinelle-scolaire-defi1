"""Indicateurs de flux calculés à partir des effectifs et des redoublants.

Méthode de la cohorte reconstituée, pour une entité, une classe g et le passage
de l'année t à l'année t+1 :

    promus(g)       = effectif(g+1, t+1) - redoublants(g+1, t+1)
    redoublants(g)  = redoublants(g, t+1)
    abandon(g)      = effectif(g, t) - promus(g) - redoublants(g)

Les taux rapportent ces quantités à effectif(g, t). Le CM2 est exclu : la
promotion hors du primaire n'est pas observée. Les valeurs négatives sont
conservées ; les annuaires les ramènent à zéro, ce qui biaise l'abandon vers le haut.

L'abandon ainsi mesuré est un abandon apparent : il inclut les départs nets
vers d'autres provinces, ce qui compte dans un contexte de déplacements.

Tout agrégat (cycle, région, nouveau découpage) est calculé en additionnant les
effectifs avant de diviser, jamais en moyennant des taux.
"""

from __future__ import annotations

import pandas as pd

NIVEAUX = ["CP1", "CP2", "CE1", "CE2", "CM1", "CM2"]
CLASSES_FLUX = NIVEAUX[:-1]


def effectifs_retenus(effectifs: pd.DataFrame) -> pd.DataFrame:
    """Une valeur par année, entité, classe et sexe : celle de l'édition la plus récente qui la donne.

    Les éditions successives révisent parfois l'année en cours ; la plus récente est retenue.
    """
    cle = ["annee_scolaire", "entite_pcode", "niveau", "sexe"]
    trie = effectifs.sort_values("annee_publication")
    return trie.drop_duplicates(cle, keep="last").rename(columns={"annee_publication": "edition_retenue"})


def annee_suivante(annee: str) -> str:
    debut = int(annee[:4]) + 1
    return f"{debut}-{debut + 1}"


def flux_par_classe(effectifs: pd.DataFrame) -> pd.DataFrame:
    """Effectifs de départ, promus, redoublants et abandons par classe, pour chaque passage t vers t+1."""
    e = effectifs[effectifs["niveau"].isin(NIVEAUX)]
    cle = ["entite_pcode", "niveau_geo", "sexe"]
    t0 = e[cle + ["annee_scolaire", "niveau", "effectif"]].rename(columns={"effectif": "effectif_t"})

    suivant = e[cle + ["annee_scolaire", "niveau", "effectif", "redoublants"]].copy()
    suivant["annee_scolaire"] = suivant["annee_scolaire"].map(
        lambda a: f"{int(a[:4]) - 1}-{int(a[:4])}")  # ramené à l'année t

    meme = suivant.rename(columns={"redoublants": "redoublants_t1"})[cle + ["annee_scolaire", "niveau", "redoublants_t1"]]
    superieure = suivant.copy()
    superieure["niveau"] = superieure["niveau"].map(
        {n: NIVEAUX[i - 1] for i, n in enumerate(NIVEAUX) if i > 0})
    superieure = superieure.dropna(subset=["niveau"]).rename(
        columns={"effectif": "effectif_sup_t1", "redoublants": "redoublants_sup_t1"})

    f = (t0[t0["niveau"].isin(CLASSES_FLUX)]
         .merge(meme, on=cle + ["annee_scolaire", "niveau"], how="inner")
         .merge(superieure, on=cle + ["annee_scolaire", "niveau"], how="inner"))
    f["promus"] = f["effectif_sup_t1"] - f["redoublants_sup_t1"]
    f["redoublants"] = f["redoublants_t1"]
    f["abandons"] = f["effectif_t"] - f["promus"] - f["redoublants"]
    f["annee_suivante"] = f["annee_scolaire"].map(annee_suivante)
    return f[cle + ["annee_scolaire", "annee_suivante", "niveau", "effectif_t", "promus", "redoublants", "abandons"]]


def taux(flux: pd.DataFrame, par: list[str]) -> pd.DataFrame:
    """Taux de promotion, redoublement et abandon, après somme des effectifs sur les groupes ``par``."""
    s = flux.groupby(par, dropna=False)[["effectif_t", "promus", "redoublants", "abandons"]].sum().reset_index()
    for quantite, nom in [("promus", "taux_promotion"), ("redoublants", "taux_redoublement"),
                          ("abandons", "taux_abandon")]:
        s[nom] = (100 * s[quantite] / s["effectif_t"]).round(2)
    return s
