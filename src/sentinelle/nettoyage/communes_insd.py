"""Effectifs scolaires par commune : annuaires statistiques régionaux 2024 de l'INSD.

Dans ces annuaires, chaque tableau communal se présente ainsi :

    Tableau 02.04.12 : Effectifs des élèves du primaire par commune et par sexe     (titre, parfois sur 2 lignes)
    2014/2015 | 2015/2016 | … | 2018/2019                                           années en colonnes
    Bagassi                                                                         commune
    Filles | 3 186 | 3 307 | …                                                      une ligne par modalité
    Garçons | 3 070 | …
    Ensemble | 6 256 | …

Chaque page est découpée en blocs, un bloc par titre de tableau. Le type du bloc se lit
sur son titre complet (élèves, enseignants, salles, salles sous paillote, écoles, écoles
fermées pour insécurité ; élèves du post-primaire). Les tableaux des résultats au CEP, des
taux, du technique et de la petite enfance, qui parlent aussi d'élèves, sont écartés.

Les noms de commune sont reconnus parmi les communes de la région du fichier : égalité des
noms normalisés, orthographes connues, puis orthographe voisine. Une ligne de province ou de
total clôt la commune en cours. Une valeur contradictoire (même commune, année, indicateur
et modalité, deux valeurs) est écartée et notée au journal.

Sortie : ``fait_insd_commune``, une valeur par année scolaire, commune, indicateur et modalité.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

import pandas as pd

from .conditions_scolarisation import _sans_accent
from .dgess import _trier
from .outils import Journal, cellules, colonnes_cellules, en_nombre, lire_extrait, normaliser_nom

TABLE = "fait_insd_commune"
JEUX = ("insd_primaire_commune", "insd_post_primaire_commune")
# Type d'un tableau d'après les mots de son titre, du plus précis au plus général.
TYPES_PRIMAIRE = [("ecoles_fermees", ("FERM",)), ("salles_paillote", ("PAILLOT",)), ("salles", ("SALLES",)),
                  ("enseignants", ("ENSEIGNANTS",)), ("ecoles", ("ECOLES",)), ("eleves", ("ELEVES",))]
TYPES_POST_PRIMAIRE = [("eleves_post_primaire", ("ELEVES", "POST")), ("eleves_secondaire", ("ELEVES", "SECONDAIRE"))]
ECARTES = ("CEP", "CERTIFICAT", "ADMIS", "PROPORTION", "TAUX", "TECHNIQUE", "PETITE ENFANCE", "PRESENTE")
MODALITES = {"FILLES": "F", "FILLE": "F", "FEMMES": "F", "FEMME": "F", "GARCONS": "G", "GARCON": "G",
             "HOMMES": "G", "HOMME": "G",
             "PUBLIC": "public", "PRIVE": "prive", "COMMUNAUTAIRE": "communautaire", "ENSEMBLE": "T", "TOTAL": "T"}
# Orthographes des annuaires éloignées de celles du COD-AB.
ORTHOGRAPHES = {"DOKUY": "DOKUI", "OURY": "OURI", "GOUNGHIN": "GOUNGUEN", "SABCE": "SABSE", "CASSOU": "KASSOU",
                "THYOU": "THIOU", "IPELCE": "IPELSE", "COALLA": "KOALA", "BEKUY": "BEKUI", "BONY": "BONI",
                "KSAMBLA": "KARANGASSOSAMBLA", "KVIGUE": "KARANGASSOVIGUE", "BANH": "BAHN", "BOKIN": "BOKEN",
                "GOURCY": "GOURSI", "BOUDRY": "BOUDRI", "SALOGHO": "SAOLGO", "TOEGHIN": "TOEGUEN"}
_ANNEE = re.compile(r"^(?:20)?(\d{2})\s*[/-]\s*(?:20)?(\d{2})$")


def _annee(texte: str) -> tuple[int, int] | None:
    m = _ANNEE.match(texte.replace(" ", ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _en_tete(paires: list[tuple[int, int]]) -> list[str]:
    """Années scolaires d'un en-tête ; une étiquette impossible (« 17/16 ») suit l'année précédente."""
    annees = []
    for i, (debut, fin) in enumerate(paires):
        if fin != debut + 1 and annees:
            debut = int(annees[-1][2:4]) + 1
        annees.append(f"20{debut:02d}-20{debut + 1:02d}")
    return annees


def _type(titre: str, jeu: str) -> str | None:
    t = _sans_accent(titre)
    if "COMMUNE" not in t or any(m in t for m in ECARTES):
        return None
    secondaire = "POST" in t or "SECONDAIRE" in t
    types = TYPES_POST_PRIMAIRE if jeu == "insd_post_primaire_commune" else TYPES_PRIMAIRE
    if (jeu == "insd_post_primaire_commune") != secondaire:
        return None
    return next((nom for nom, mots in types if all(m in t for m in mots)), None)


# Dimension d'une modalité : élèves et enseignants sont publiés par sexe et par statut, parfois dans un même
# tableau ; la ligne « Ensemble » prend la dimension des modalités qui la précèdent.
DIMENSIONS = {"F": "sexe", "G": "sexe", "public": "statut", "prive": "statut", "communautaire": "statut"}


class _Communes:
    """Reconnaissance des communes d'une région (ancien découpage)."""

    def __init__(self, communes: pd.DataFrame):
        self.par_region = {r: list(zip(g["commune_pcode"], g["commune_nom"].map(normaliser_nom)))
                           for r, g in communes.groupby("region_ancienne_pcode")}
        self.provinces = set(communes["province_ancienne_nom"].map(normaliser_nom))
        self.regions = dict(zip(communes["region_ancienne_nom"].map(normaliser_nom), communes["region_ancienne_pcode"]))
        self.rapprochements: list[dict] = []

    def region_du_fichier(self, fichier: str) -> str | None:
        n = normaliser_nom(re.sub(r"(?i)\.pdf$|_\d+$", "", fichier).split("2024")[-1])
        n = re.sub(r"^(DELA|DE|DES|DU)?(REGION)?(DELA|DES|DU|DE)?", "", n)
        return self.regions.get(n) or next((c for nom, c in self.regions.items() if n.startswith(nom) or nom == n), None)

    def __call__(self, nom: str, region: str) -> str | None:
        n = normaliser_nom(re.sub(r"(?i)^commune\s+d[e']\s*", "", nom))
        n = ORTHOGRAPHES.get(n, n)
        if n in self.provinces or n.startswith(("TOTAL", "PROVINCE", "REGION")):
            return None
        candidats = self.par_region.get(region, [])
        exact = [c for c, nn in candidats if nn == n]
        if len(exact) == 1:
            return exact[0]
        scores = [(SequenceMatcher(None, n, nn).ratio(), c, nn) for c, nn in candidats]
        if scores:
            score, code, voisin = max(scores)
            if score >= 0.85:
                self.rapprochements.append({"nom_lu": nom, "commune_pcode": code, "nom_retenu": voisin,
                                            "similarite": round(score, 3)})
                return code
        return None


def lire_communes_insd(communes: pd.DataFrame, journal: Journal) -> pd.DataFrame:
    reconnaitre = _Communes(communes)
    valeurs = []
    for jeu in JEUX:
        brut = _trier(lire_extrait(jeu))
        colonnes = colonnes_cellules(brut)
        for fichier, document in brut.groupby("source_fichier", sort=False):
            region = reconnaitre.region_du_fichier(fichier)
            if region is None:
                journal.noter(TABLE, "fichier écarté", "région du fichier non reconnue", source=fichier)
                continue
            type_bloc, titre, annees, commune, dimension = None, "", [], None, "sexe"
            for _, row in document.iterrows():
                cel = cellules(row, colonnes)
                if not cel:
                    continue
                texte = " ".join(cel)
                # Titre : « Tableau … », ou, dans certains annuaires (Sahel), « Effectifs des … » sans préfixe.
                sans_valeur = all(pd.isna(en_nombre(c)) for c in cel)
                if re.match(r"(?i)^\s*tableau", texte) or (
                        sans_valeur and len(texte) > 30
                        and re.match(r"(?i)^\s*(effectifs?|nombre|r[ée]partition|proportion|taux)\s+d", texte)):
                    titre, type_bloc, annees, commune = texte, _type(texte, jeu), [], None
                    dimension = "statut" if "STATUT" in _sans_accent(texte) else "sexe"
                    continue
                # Titre sur deux lignes : la suite complète le titre tant qu'aucune année n'est lue.
                if titre and not annees and type_bloc is None and not any(_annee(c) for c in cel) \
                        and all(pd.isna(en_nombre(c)) for c in cel):
                    titre += " " + texte
                    type_bloc = _type(titre, jeu)
                    dimension = "statut" if "STATUT" in _sans_accent(titre) else "sexe"
                    continue
                if type_bloc is None:
                    continue
                lues = [_annee(c) for c in cel]
                if all(lues):
                    annees = _en_tete(lues)
                    if any(f != d + 1 for d, f in lues):
                        journal.noter(TABLE, "correction", "année impossible dans l'en-tête, remplacée d'après la "
                                      "précédente", source=fichier, page=str(row["page"]), avant=texte,
                                      apres=" ".join(annees))
                    continue
                nombres = [en_nombre(c) if _sans_accent(c) not in {"ND", "NP"} else float("nan") for c in cel]
                premier = next((i for i, c in enumerate(cel)
                                if not pd.isna(nombres[i]) or _sans_accent(c) in {"ND", "NP"}), len(cel))
                libelles = cel[:premier]
                modalite = MODALITES.get(_sans_accent(libelles[-1]).strip()) if libelles else None
                nom = " ".join(libelles[:-1] if modalite else libelles)
                if nom:
                    trouve = reconnaitre(nom, region)
                    if trouve or premier == len(cel):
                        commune = trouve
                if premier == len(cel) or commune is None or not annees:
                    continue
                serie = nombres[premier:]
                if len(serie) != len(annees):
                    journal.noter(TABLE, "ligne écartée", f"{len(serie)} valeurs pour {len(annees)} années",
                                  source=fichier, page=str(row["page"]), avant=texte)
                    continue
                indicateur = type_bloc
                if type_bloc.startswith(("eleves", "enseignants")):
                    dimension = DIMENSIONS.get(modalite, dimension)
                    indicateur = f"{type_bloc}_par_{dimension}"
                for annee, valeur in zip(annees, serie):
                    valeurs.append({"annee_scolaire": annee, "commune_pcode": commune, "indicateur": indicateur,
                                    "modalite": modalite or "T", "valeur": valeur, "source_fichier": fichier,
                                    "page": str(row["page"])})
    table = pd.DataFrame(valeurs)
    cles = ["annee_scolaire", "commune_pcode", "indicateur", "modalite"]
    distinctes = table.groupby(cles)["valeur"].transform(lambda v: v.nunique(dropna=False))
    for _, ligne in table[distinctes > 1].drop_duplicates(cles).iterrows():
        journal.noter(TABLE, "valeur écartée", "valeurs contradictoires pour une même commune, année et modalité",
                      source=ligne["source_fichier"], page=ligne["page"],
                      avant=f"{ligne['commune_pcode']} {ligne['annee_scolaire']} {ligne['indicateur']} {ligne['modalite']}")
    for r in reconnaitre.rapprochements:
        journal.noter(TABLE, "rapprochement", f"orthographe voisine de {r['nom_retenu']} ({r['similarite']})",
                      avant=r["nom_lu"], apres=r["commune_pcode"])
    return table[distinctes == 1].drop_duplicates(cles).reset_index(drop=True)


def controler(table: pd.DataFrame, communes: pd.DataFrame) -> dict[str, tuple[bool, str]]:
    eleves = table[table["indicateur"].str.startswith("eleves_par") & (table["modalite"] == "T")]
    attendues = communes.groupby("region_ancienne_pcode")["commune_pcode"].nunique()
    region_de = communes.set_index("commune_pcode")["region_ancienne_pcode"]
    lues = eleves.assign(r=eleves["commune_pcode"].map(region_de)).groupby("r")["commune_pcode"].nunique()
    part = (lues / attendues.reindex(lues.index)).round(2)
    large = table[table["indicateur"] == "eleves_par_sexe"].pivot_table(
        index=["annee_scolaire", "commune_pcode"], columns="modalite", values="valeur")
    sexes = large.dropna(subset=["F", "G", "T"]) if {"F", "G", "T"} <= set(large.columns) else large.iloc[:0]
    ecart = (sexes["F"] + sexes["G"] - sexes["T"]).abs() if len(sexes) else pd.Series(dtype=float)
    post = table[table["indicateur"].str.startswith("eleves_post_primaire")]["commune_pcode"].nunique()
    return {
        "communes_insd_couverture": (len(lues) == 13 and bool((part >= 0.6).all()),
                                     f"{len(lues)} régions ; communes lues / attendues : "
                                     + ", ".join(f"{r} {v:.0%}" for r, v in part.items())),
        "communes_insd_filles_plus_garcons": (bool((ecart <= 1).mean() >= 0.95) if len(ecart) else False,
                                              f"filles + garçons = ensemble pour {int((ecart <= 1).sum())} lignes sur "
                                              f"{len(ecart)}"),
        "communes_insd_post_primaire": (post >= 250, f"élèves du post-primaire lus pour {post} communes"),
    }
