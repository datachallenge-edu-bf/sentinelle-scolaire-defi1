"""Tableaux de bord DGESS du post-primaire et du secondaire : indicateurs par région et pour le pays.

Sources : tableaux de bord 2023 et 2024 (Data Pack) et 2025 (téléchargé par l'équipe).

Deux lectures :

- les pages régionales (« Effectifs des élèves au post-primaire », « Taux brut de
  scolarisation au secondaire »…) : une ligne par région puis le pays, avec garçons,
  filles et ensemble, pour l'année indiquée dans le sous-titre ;
- la table nationale des indicateurs clés, qui donne cinq années par indicateur : elle
  complète les années absentes des pages régionales, pour le pays seulement.

Un total national n'est jamais réparti entre régions, et les chiffres des graphiques ne
sont pas lus. Table longue : ``fait_tableau_bord_secondaire``.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .dgess import Identification, _trier
from .outils import Journal, cellules, colonnes_cellules, en_nombre, lire_extrait, normaliser_nom

JEU = "dgess_tableaux_de_bord_post_primaire"
TABLE = "fait_tableau_bord_secondaire"
SEXES = ["garcons", "filles", "ensemble"]
CLE = ["annee_scolaire", "entite_pcode", "ordre", "indicateur", "sexe"]

# Titre de page régionale (normalisé) -> (ordre, indicateur).
PAGES_REGIONALES = {
    "EFFECTIFSDESELEVESAUPOSTPRIMAIRE": ("post_primaire", "eleves"),
    "EFFECTIFSDESELEVESDUSECONDAIRE": ("secondaire", "eleves"),
    "TAUXBRUTDADMISSIONAUPOSTPRIMAIRE": ("post_primaire", "tba"),
    "TAUXBRUTDADMISSIONAUSECONDAIRE": ("secondaire", "tba"),
    "TAUXBRUTDESCOLARISATIONAUPOSTPRIMAIRE": ("post_primaire", "tbs"),
    "TAUXBRUTDESCOLARISATIONAUSECONDAIRE": ("secondaire", "tbs"),
    "TAUXDACHEVEMENTAUPOSTPRIMAIRE": ("post_primaire", "taux_achevement"),
    "TAUXDACHEVEMENTAUSECONDAIRE": ("secondaire", "taux_achevement"),
}
# Numéro de ligne de la table des indicateurs clés -> (ordre, indicateur).
LIGNES_NATIONALES = {
    "1a": ("post_primaire", "eleves"), "1b": ("secondaire", "eleves"),
    "2a": ("post_primaire", "tba"), "2b": ("secondaire", "tba"),
    "3a": ("post_primaire", "tbs"), "3b": ("secondaire", "tbs"),
    "10": ("post_primaire", "taux_achevement"), "12": ("secondaire", "taux_achevement"),
}
_ANNEE_SOUS_TITRE = re.compile(r"en (20\d\d)\s*/\s*(20\d\d)")
_ANNEES_TABLE = re.compile(r"(20\d{2})/(20\d{2})")
_NUMERO_LIGNE = re.compile(r"^(\d+[ab]?)(1)?[. ]")


def valeur(texte: str) -> float | None:
    """Nombre lu dans une cellule ; NaN si la valeur est déclarée indisponible ; None si ce n'est pas un nombre.

    Deux écritures propres au tableau de bord 2025 : le point des milliers (« 29.241 ») et la
    décimale perdue à la conversion (« 114, », dont la partie entière est gardée).
    """
    t = re.sub(r"\s", "", texte).replace("%", "")
    if normaliser_nom(t) in {"ND", "NA", "NP"} or t in {"-", "–"}:
        return np.nan
    if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", t):
        return float(t.replace(".", ""))
    if re.fullmatch(r"-?\d+(?:[.,]\d*)?", t):
        return en_nombre(t.rstrip(",."))
    return None


def _pages(brut: pd.DataFrame):
    """(fichier, page, lignes) avec, pour chaque ligne, ses cellules non vides et leur texte réuni."""
    brut = _trier(brut)
    colonnes = colonnes_cellules(brut)
    brut = brut.assign(morceaux=brut.apply(lambda r: cellules(r, colonnes), axis=1))
    brut = brut[brut["morceaux"].map(len) > 0]
    brut = brut.assign(texte=brut["morceaux"].map(" ".join))
    for (fichier, page), lignes in brut.groupby(["source_fichier", "_page"], sort=False):
        yield fichier, str(int(page)), lignes


def _page_regionale(fichier: str, page: str, lignes: pd.DataFrame, identifier: Identification,
                    journal: Journal) -> list[dict]:
    titre = normaliser_nom(lignes["texte"].iloc[0])
    if titre not in PAGES_REGIONALES:
        return []
    ordre, indicateur = PAGES_REGIONALES[titre]
    annee = next((f"{m.group(1)}-{m.group(2)}" for m in map(_ANNEE_SOUS_TITRE.search, lignes["texte"].head(4)) if m),
                 None)
    if annee is None:
        if not lignes["texte"].map(normaliser_nom).str.contains("SAILLANT").any():  # page de commentaires
            journal.noter(TABLE, "signalement", "année introuvable dans le sous-titre", source=fichier, page=page)
        return []
    resultat, entites = [], set()
    for ligne in lignes.itertuples():
        if len(ligne.morceaux) < 4:
            continue
        lieu = identifier(ligne.morceaux[0])
        if lieu is None or lieu[1] not in ("region_ancienne", "pays"):
            continue
        valeurs = [valeur(m) for m in ligne.morceaux[1:4]]
        if any(v is None for v in valeurs):
            journal.noter(TABLE, "signalement", "ligne de région sans trois valeurs", source=fichier, page=page,
                          ligne=str(ligne.ligne), avant=ligne.texte)
            continue
        entites.add(lieu[0])
        resultat += [{"annee_scolaire": annee, "entite_pcode": lieu[0],
                      "niveau": "pays" if lieu[1] == "pays" else "region", "ordre": ordre,
                      "indicateur": indicateur, "sexe": sexe, "valeur": v, "source_fichier": fichier, "page": page}
                     for sexe, v in zip(SEXES, valeurs)]
        if lieu[1] == "pays":
            break  # la suite de la page porte des graphiques
    if len(entites) != 14:
        journal.noter(TABLE, "signalement", f"{len(entites)} entités lues sur 14 (13 régions et le pays)",
                      source=fichier, page=page)
    return resultat


def _table_nationale(fichier: str, page: str, lignes: pd.DataFrame) -> list[dict]:
    """Table des indicateurs clés : cinq années par ligne, pour le pays."""
    if not lignes["texte"].head(2).map(normaliser_nom).eq("INDICATEURSCLES").any():
        return []
    annees = list(dict.fromkeys(f"{a}-{b}" for t in lignes["texte"].head(5) for a, b in _ANNEES_TABLE.findall(t)))
    if len(annees) != 5:
        raise ValueError(f"En-tête des cinq années absent : {fichier}, page {page}")
    resultat, courant, sexe = [], None, "ensemble"
    for ligne in lignes.itertuples():
        numero = _NUMERO_LIGNE.match(ligne.texte)
        if numero and re.search(r"[A-Z]", normaliser_nom(ligne.morceaux[0])):
            courant = LIGNES_NATIONALES.get(numero.group(1))
            sexe = "filles" if numero.group(2) else "ensemble"
            if courant and courant[1] == "eleves" and sexe == "filles":
                courant = None  # part des filles en %, pas un effectif
        elif normaliser_nom(ligne.texte).startswith("DONTFILLES"):
            sexe = "filles"
        if courant is None:
            continue
        valeurs = [v for v in map(valeur, ligne.morceaux) if v is not None]
        if len(valeurs) < len(annees):
            continue
        ordre, indicateur = courant
        resultat += [{"annee_scolaire": a, "entite_pcode": "BF", "niveau": "pays", "ordre": ordre,
                      "indicateur": indicateur, "sexe": sexe, "valeur": v, "source_fichier": fichier, "page": page}
                     for a, v in zip(annees, valeurs)]
        if sexe == "filles":
            courant = None  # une valeur sans libellé ne prolonge pas la ligne des filles
    return resultat


def lire(identifier: Identification, journal: Journal) -> pd.DataFrame:
    """Indicateurs des pages régionales, complétés pour le pays par la table des indicateurs clés."""
    regionales, nationales = [], []
    for fichier, page, lignes in _pages(lire_extrait(JEU)):
        if fichier.startswith(("CNS56", "DGESS_Tableau_de_bord")):
            regionales += _page_regionale(fichier, page, lignes, identifier, journal)
        if fichier.startswith("DGESS_Tableau_de_bord"):
            nationales += _table_nationale(fichier, page, lignes)
    table = pd.DataFrame(regionales + nationales)  # les pages régionales priment
    doublons = int(table.duplicated(CLE).sum())
    if doublons:
        journal.noter(TABLE, "signalement", f"{doublons} valeurs déjà lues sur une page régionale : la première est gardée")
    return table.drop_duplicates(CLE).sort_values(CLE).reset_index(drop=True)


def controler(table: pd.DataFrame) -> dict[str, tuple[bool, str]]:
    eleves = table[table["indicateur"] == "eleves"].pivot_table(
        index=["annee_scolaire", "entite_pcode", "ordre"], columns="sexe", values="valeur").dropna()
    ecart_sexes = (eleves["garcons"] + eleves["filles"] - eleves["ensemble"]).abs()
    ensemble = table[(table["indicateur"] == "eleves") & (table["sexe"] == "ensemble")]
    regions = ensemble[ensemble["niveau"] == "region"].groupby(["annee_scolaire", "ordre"])["valeur"].sum()
    pays = ensemble[ensemble["niveau"] == "pays"].set_index(["annee_scolaire", "ordre"])["valeur"].reindex(regions.index)
    ecart_pays = ((regions - pays) / pays).abs()
    regionaux = table[table["niveau"] == "region"][["annee_scolaire", "ordre", "indicateur"]].drop_duplicates()
    couverture = table.merge(regionaux).groupby(["annee_scolaire", "ordre", "indicateur"])["entite_pcode"].nunique()
    return {
        "tableaux_de_bord_secondaire_14_entites": (
            bool((couverture == 14).all()),
            f"{len(couverture)} indicateurs × ordres × années régionaux, tous à 13 régions et le pays"),
        "tableaux_de_bord_secondaire_garcons_plus_filles": (
            bool((ecart_sexes <= 1).mean() >= 0.95),
            f"garçons + filles = ensemble (à 1 près) pour {int((ecart_sexes <= 1).sum())} lignes sur {len(ecart_sexes)}"),
        "tableaux_de_bord_secondaire_regions_egal_pays": (
            bool((ecart_pays <= 0.001).all()),
            "élèves, somme des 13 régions / pays : " + ", ".join(
                f"{a} {o} {v:.2%}" for (a, o), v in ecart_pays.items())),
    }
