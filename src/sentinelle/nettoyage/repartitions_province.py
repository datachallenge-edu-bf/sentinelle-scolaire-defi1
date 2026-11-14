"""Répartitions par province sur plusieurs lignes : élèves et nouveaux entrants par âge, enseignants.

Dans ces tableaux des annuaires DGESS, chaque province occupe une ligne de nom suivie
d'une ligne par modalité (filles, garçons, total, pourcentage ; ou femmes, hommes,
total), dont la première cellule répète le libellé (« Filles Filles Filles … »). Une
ligne de modalité est rattachée à la dernière province nommée ; elle n'est retenue que
si elle porte le nombre de valeurs attendu.

- élèves par âge (moins de 6 ans à plus de 15 ans) : retard scolaire ;
- nouveaux entrants au CP1 par âge (moins de 6 ans à plus de 10 ans) : entrée tardive ;
- enseignants par sexe, âge et années d'expérience : part des enseignantes, des débutants.
"""

from __future__ import annotations

import re

import pandas as pd

from .conditions_scolarisation import _sans_accent, _sous_tableau
from .dgess import Identification, _trier
from .outils import Journal, cellules, colonnes_cellules, en_nombre, est_nombre, lire_extrait

TABLE = "fait_repartitions_province"
_AGES = ["moins_6", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "plus_15", "total"]
SECTIONS = {
    "ages_eleves": ("dgess_ages_province", r"REPARTITION DES ELEVES PAR AGE ET SEXE", [f"age_{a}" for a in _AGES]),
    "ages_entrants": ("dgess_ages_province", r"NOUVEAUX ENTRANTS PAR AGE",
                      [f"age_{a}" for a in ["moins_6", "6", "7", "8", "9", "10", "plus_10", "total"]]),
    "enseignants": ("dgess_enseignants_province", r"EXPERIENCE",
                    ["age_moins_30", "age_30_40", "age_41_50", "age_plus_50", "age_indetermine", "total",
                     "experience_1_5", "experience_6_10", "experience_11_15", "experience_plus_15",
                     "experience_indeterminee"]),
}
MODALITES = {"FILLES": "F", "GARCONS": "G", "TOTAL": "T", "%": "pct", "FEMMES": "F", "HOMMES": "H"}


def _modalite(premiere_cellule: str) -> str | None:
    mots = set(_sans_accent(premiere_cellule).split())
    return MODALITES[mots.pop()] if len(mots) == 1 and next(iter(mots)) in MODALITES else None


def lire_repartitions(identifier: Identification, journal: Journal) -> pd.DataFrame:
    par_jeu: dict[str, dict] = {}
    for nom, definition in SECTIONS.items():
        par_jeu.setdefault(definition[0], {})[nom] = definition
    lignes = []
    for jeu, sections in par_jeu.items():
        brut = _trier(lire_extrait(jeu))
        colonnes = colonnes_cellules(brut)
        brut["_texte"] = brut[colonnes].apply(lambda r: " ".join(v.strip() for v in r if v.strip()), axis=1)
        for fichier, document in brut.groupby("source_fichier", sort=False):
            edition = document["source_periode"].iloc[0]
            tetes = document.groupby("_page")["_texte"].apply(lambda s: _sans_accent(" ".join(s.head(8))))
            section, sous_tableau, province = None, "ensemble", None
            for page, contenu in document.groupby("_page", sort=True):
                trouvee = next((nom for nom, (_j, motif, _c) in sections.items() if re.search(motif, tetes[page])), None)
                if trouvee != section:
                    section, sous_tableau, province = trouvee, "ensemble", None
                if section is None:
                    continue
                noms = sections[section][2]
                for _, row in contenu.iterrows():
                    cel = cellules(row, colonnes)
                    if not cel:
                        continue
                    st = _sous_tableau(" ".join(cel))
                    if st:
                        sous_tableau, province = st, None
                        continue
                    if len(cel) == 1 and not est_nombre(cel[0]):
                        trouve = identifier(cel[0])
                        province = trouve[0] if trouve and trouve[1] == "province_ancienne" else None
                        continue
                    modalite = _modalite(cel[0])
                    if modalite is None or province is None:
                        continue
                    valeurs = cel[1:]
                    if len(valeurs) != len(noms) or not all(est_nombre(v) for v in valeurs):
                        journal.noter(TABLE, "ligne écartée", f"{section} : {len(valeurs)} valeurs au lieu de {len(noms)}",
                                      source=fichier, page=str(page), avant=" | ".join(cel)[:150])
                        continue
                    for variable, valeur in zip(noms, valeurs):
                        lignes.append({"annee_scolaire": edition, "section": section, "sous_tableau": sous_tableau,
                                       "entite_pcode": province, "modalite": modalite, "variable": variable,
                                       "valeur": en_nombre(valeur), "source_fichier": fichier, "page": page})
    table = pd.DataFrame(lignes)
    cles = ["annee_scolaire", "section", "sous_tableau", "entite_pcode", "modalite", "variable"]
    return table.drop_duplicates(cles, keep="first").sort_values(cles).reset_index(drop=True)


def controler(table: pd.DataFrame) -> dict[str, tuple[bool, str]]:
    resultats = {}
    couverture = table[table["modalite"] == "T"].groupby(["section", "annee_scolaire"])["entite_pcode"].nunique().unstack()
    incompletes = [(s, a, int(v)) for s, ligne in couverture.iterrows() for a, v in ligne.items() if v == v and v < 44]
    resultats["repartitions_45_provinces"] = (
        not incompletes, f"{couverture.shape[0]} sections × {couverture.shape[1]} éditions ; "
        + ("toutes à 44 ou 45 provinces" if not incompletes else "incomplètes : " + ", ".join(
            f"{s} {a} ({v})" for s, a, v in incompletes[:8])))
    large = table[table["variable"].str.endswith("total")].pivot_table(
        index=["annee_scolaire", "section", "sous_tableau", "entite_pcode"], columns="modalite", values="valeur")
    sexes = large[["F", "G"]].sum(axis=1, min_count=2) if "G" in large else large[["F", "H"]].sum(axis=1, min_count=2)
    if "H" in large:
        sexes = sexes.fillna(large[["F", "H"]].sum(axis=1, min_count=2))
    ecart = (sexes - large["T"]).abs().dropna()
    resultats["repartitions_sexes_egal_total"] = (bool((ecart == 0).mean() >= 0.95),
                                                  f"filles + garçons (femmes + hommes) = total pour {int((ecart == 0).sum())} "
                                                  f"lignes sur {len(ecart)}")
    return resultats
