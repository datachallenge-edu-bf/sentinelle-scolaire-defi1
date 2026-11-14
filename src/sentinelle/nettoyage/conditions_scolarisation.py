"""Conditions de scolarisation par province : tableaux « une ligne par province » des annuaires DGESS.

Une vingtaine de sections des annuaires du primaire donnent, pour chaque province et
chaque édition (2017-2018 à 2024-2025), une ligne de valeurs dont le nombre ne change
pas d'une édition à l'autre : équipement des écoles, distance parcourue par les élèves,
taille des écoles, logements de maîtres, manuels et mobilier, profession des parents,
surface, ancienneté et état des salles, taux d'admission, de scolarisation et
d'achèvement, résultats au CEP.

Chaque section est décrite par le motif de son titre, les noms de ses colonnes et donc
sa largeur. Le sous-tableau (public, privé, ensemble, urbain, rural) est lu dans
l'intertitre « V.4.1 Public ». Une ligne n'est retenue que si elle commence par le nom
d'une province reconnue et porte exactement le nombre de valeurs attendu ; les autres
lignes chiffrées sont consignées dans le journal.
"""

from __future__ import annotations

import re

import pandas as pd

from .dgess import Identification, _trier
from .outils import Journal, cellules, colonnes_cellules, en_nombre, est_nombre, lire_extrait, normaliser_nom

TABLE = "fait_conditions_scolarisation"
_SALLES = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "plus_10"]
_TAUX = ["denominateur_g", "denominateur_f", "denominateur_t", "numerateur_g", "numerateur_f", "numerateur_t",
         "taux_g", "taux_f", "taux_t"]

# Section : (jeu collecté, motif du titre dans l'en-tête de page, colonnes).
SECTIONS = {
    "equipement": ("dgess_equipement_province", r"EQUIPEMENT DES ECOLES",
                   ["ecoles", "ecoles_eau_potable", "ecoles_electricite", "ecoles_latrines", "ecoles_jardins",
                    "ecoles_cantines", "ecoles_terrain_sport", "ecoles_clotures"]),
    "distance": ("dgess_distance_province", r"DISTANCE PARCOURUE",
                 ["pct_eleves_moins_3km", "pct_eleves_3_5km", "pct_eleves_plus_5km", "eleves"]),
    "taille_ecoles": ("dgess_taille_ecoles_province", r"TAILLE DES ECOLES",
                      ["ecoles", "salles"] + [f"ecoles_{n}_salles" for n in _SALLES]),
    "logements_maitres": ("dgess_logements_maitres_province", r"LOGEMENTS? DE MA",
                          ["maitres", "ecoles_sans_logement", "logements", "logements_bon_etat"]),
    "manuels": ("dgess_manuels_mobilier_province", r"MANUELS",
                ["manuels_lecture", "manuels_calcul", "manuels_histoire", "manuels_geographie", "manuels_sciences",
                 "manuels_grammaire", "manuels_autres", "eleves"]),
    "mobilier": ("dgess_manuels_mobilier_province", r"MOBILIERS? (DES )?ELEVES",
                 ["ecoles", "ecoles_tables_bancs_suffisants", "ecoles_tables_bancs_insuffisants",
                  "deficit_places_assises"]),
    # Les intitulés des colonnes 3 à 9 ont changé d'une édition à l'autre : seules les deux premières sont nommées.
    "profession_parents": ("dgess_profession_parents_province", r"PROFESSION DES PARENTS",
                           ["parents_cultivateurs", "parents_eleveurs"] + [f"parents_autre_{i}" for i in range(3, 10)]),
    "surface_salles": ("dgess_salles_province", r"SURFACE DES SALLES",
                       ["salles_moins_40m2", "salles_40_50m2", "salles_50_60m2", "salles_60_70m2", "salles_plus_70m2",
                        "salles_surface_indeterminee", "salles", "eleves_par_classe"]),
    "anciennete_salles": ("dgess_salles_province", r"MISE EN SERVICE",
                          ["salles_avant_1965", "salles_1965_1975", "salles_1975_1985", "salles_1985_1995",
                           "salles_1995_2005", "salles_2005_2015", "salles_apres_2015", "salles_annee_indeterminee",
                           "salles"]),
    "murs": ("dgess_salles_province", r"NATURE ET ETAT DES MURS",
             ["murs_dur", "murs_semi_dur", "murs_paille_banco", "murs_nature_indeterminee", "murs_bon_etat",
              "murs_mauvais_etat", "murs_etat_indetermine", "salles"]),
    # Avant 2019-2020, la colonne « sans toit » n'existe pas : deux variantes selon la largeur.
    "toitures": ("dgess_salles_province", r"NATURE ET ETAT DES TOITURES",
                 (["toit_tole", "toit_tuiles_ciment", "toit_banco", "toit_paille", "toit_absent", "toit_bon_etat",
                   "toit_mauvais_etat", "toit_etat_indetermine", "salles"],
                  ["toit_tole", "toit_tuiles_ciment", "toit_banco", "toit_paille", "toit_bon_etat",
                   "toit_mauvais_etat", "toit_etat_indetermine", "salles"])),
    "tba": ("dgess_taux_acces_province", r"TAUX BRUT D.?ADMISSION", _TAUX),
    "tbs": ("dgess_taux_acces_province", r"TAUX BRUT DE SCOLARISATION", _TAUX),
    "tns": ("dgess_taux_acces_province", r"TAUX NET DE SCOLARISATION", _TAUX),
    "achevement": ("dgess_taux_acces_province", r"TAUX D.?ACHEVEMENT", _TAUX),
    "cep": ("dgess_cep_province", r"CERTIFICAT D.?ETUDE|\bCEP\b",
            ["presents_g", "presents_f", "presents_t", "admis_g", "admis_f", "admis_t", "taux_g", "taux_f", "taux_t"]),
}
SOUS_TABLEAUX = [(r"URBAIN\s*\+\s*RURAL|PUBLIC\s*\+\s*PRIVE|ENSEMBLE", "ensemble"), (r"URBAIN", "urbain"),
                 (r"RURAL", "rural"), (r"PRIVE", "prive"), (r"PUBLIC", "public")]
_INTERTITRE = re.compile(r"^[IVX]+\s*\.\s*\d+\s*\.\s*\d+\s*\.?\s*(.+)$")
_EXCLUS = re.compile(r"PRIORITAIRES")


def _sans_accent(texte: str) -> str:
    return normaliser_nom(texte) if False else re.sub(r"\s+", " ", texte.upper().translate(
        str.maketrans("ÉÈÊËÀÂÎÏÔÛÙÇ", "EEEEAAIIOUUC")))


def _sous_tableau(texte: str) -> str | None:
    m = _INTERTITRE.match(_sans_accent(texte))
    if not m:
        return None
    reste = m.group(1)
    return next((nom for motif, nom in SOUS_TABLEAUX if re.search(motif, reste)), None)


def _lire_jeu(jeu: str, sections: dict, identifier: Identification, journal: Journal) -> list[dict]:
    brut = _trier(lire_extrait(jeu))
    colonnes = colonnes_cellules(brut)
    brut["_texte"] = brut[colonnes].apply(lambda r: " ".join(v.strip() for v in r if v.strip()), axis=1)
    lignes = []
    for fichier, document in brut.groupby("source_fichier", sort=False):
        edition = document["source_periode"].iloc[0]
        tetes = document.groupby("_page")["_texte"].apply(lambda s: _sans_accent(" ".join(s.head(8))))
        section_courante, sous_tableau = None, "ensemble"
        for page, contenu in document.groupby("_page", sort=True):
            tete = tetes[page]
            if _EXCLUS.search(tete):
                continue
            trouvee = next((nom for nom, (_j, motif, _c) in sections.items() if re.search(motif, tete)), None)
            if trouvee != section_courante:
                section_courante, sous_tableau = trouvee, "ensemble"
            if section_courante is None:
                continue
            variantes = sections[section_courante][2]
            variantes = variantes if isinstance(variantes, tuple) else (variantes,)
            for _, row in contenu.iterrows():
                cel = cellules(row, colonnes)
                if not cel:
                    continue
                st = _sous_tableau(" ".join(cel))
                if st:
                    sous_tableau = st
                    continue
                nombres = [c for c in cel[1:] if est_nombre(c)]
                if est_nombre(cel[0]) or not nombres:
                    continue
                trouve = identifier(cel[0])
                if trouve is None or trouve[1] != "province_ancienne":
                    continue
                noms_colonnes = next((v for v in variantes if len(v) == len(cel) - 1 == len(nombres)), None)
                if noms_colonnes is None:
                    journal.noter(TABLE, "ligne écartée", f"{section_courante} : {len(cel) - 1} valeurs au lieu de "
                                  f"{' ou '.join(str(len(v)) for v in variantes)}", source=fichier, page=str(page),
                                  avant=" | ".join(cel)[:150])
                    continue
                for variable, valeur in zip(noms_colonnes, nombres):
                    lignes.append({"annee_scolaire": edition, "section": section_courante, "sous_tableau": sous_tableau,
                                   "entite_pcode": trouve[0], "variable": variable, "valeur": en_nombre(valeur),
                                   "source_fichier": fichier, "page": page})
    return lignes


def lire_conditions(identifier: Identification, journal: Journal) -> pd.DataFrame:
    """Table longue : une valeur par édition, section, sous-tableau, province et variable."""
    par_jeu: dict[str, dict] = {}
    for nom, definition in SECTIONS.items():
        par_jeu.setdefault(definition[0], {})[nom] = definition
    lignes = []
    for jeu, sections in par_jeu.items():
        lignes += _lire_jeu(jeu, sections, identifier, journal)
    table = pd.DataFrame(lignes)
    cles = ["annee_scolaire", "section", "sous_tableau", "entite_pcode", "variable"]
    doublons = table.duplicated(cles, keep="first")
    for r in table[doublons].drop_duplicates(cles[:4]).itertuples():
        journal.noter(TABLE, "ligne écartée", "province répétée dans le même sous-tableau (page imprimée deux fois)",
                      source=r.source_fichier, page=str(r.page), avant=f"{r.section} {r.sous_tableau} {r.entite_pcode}")
    return table[~doublons].sort_values(cles).reset_index(drop=True)


def controler(table: pd.DataFrame) -> dict[str, tuple[bool, str]]:
    resultats = {}
    ensemble = table[table["sous_tableau"] == "ensemble"]
    couverture = ensemble.groupby(["section", "annee_scolaire"])["entite_pcode"].nunique().unstack()
    incompletes = [(s, a, int(v)) for s, ligne in couverture.iterrows() for a, v in ligne.items() if v == v and v < 44]
    resultats["conditions_scolarisation_45_provinces"] = (
        not incompletes, f"{couverture.shape[0]} sections × {couverture.shape[1]} éditions ; "
        + ("toutes à 44 ou 45 provinces" if not incompletes else "incomplètes : " + ", ".join(
            f"{s} {a} ({v})" for s, a, v in incompletes[:8])))
    # Cohérences internes : public + privé = ensemble pour les comptages de l'équipement.
    eq = table[(table["section"] == "equipement")].pivot_table(index=["annee_scolaire", "entite_pcode", "variable"],
                                                                columns="sous_tableau", values="valeur")
    if {"public", "prive", "ensemble"} <= set(eq.columns):
        ecart = (eq["public"] + eq["prive"] - eq["ensemble"]).abs().dropna()
        resultats["conditions_scolarisation_public_plus_prive"] = (
            bool((ecart == 0).mean() >= 0.95), f"équipement : public + privé = ensemble pour {int((ecart == 0).sum())} "
            f"valeurs sur {len(ecart)}")
    taille = table[(table["section"] == "taille_ecoles") & (table["sous_tableau"] == "ensemble")].pivot_table(
        index=["annee_scolaire", "entite_pcode"], columns="variable", values="valeur")
    if not taille.empty:
        somme = taille[[f"ecoles_{n}_salles" for n in _SALLES]].sum(axis=1)
        ecart = (somme - taille["ecoles"]).abs()
        resultats["conditions_scolarisation_taille_somme_ecoles"] = (
            bool((ecart == 0).mean() >= 0.95),
            f"écoles par nombre de salles = total des écoles pour {int((ecart == 0).sum())} provinces × éditions sur {len(ecart)}")
    distance = table[(table["section"] == "distance") & table["variable"].str.startswith("pct_")].pivot_table(
        index=["annee_scolaire", "sous_tableau", "entite_pcode"], columns="variable", values="valeur")
    if not distance.empty:
        ecart = (distance.sum(axis=1) - 100).abs()
        resultats["conditions_scolarisation_distance_somme_100"] = (
            bool((ecart <= 0.5).mean() >= 0.95), f"parts de la distance sommant à 100 % à 0,5 point près : "
            f"{int((ecart <= 0.5).sum())} sur {len(ecart)}")
    return resultats
