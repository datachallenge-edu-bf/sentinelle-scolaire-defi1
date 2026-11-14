"""Lecture complète de la base principale DGESS (préscolaire et primaire, 2015-2016 à 2024-2025).

Le classeur compte 14 feuilles et 21 tableaux : effectifs par région, statut, milieu,
niveau et sexe, nouveaux inscrits au CP1, taux bruts d'admission et de scolarisation,
taux d'achèvement, réussite au CEP, indices de parité, écoles, structures et salles
du préscolaire. Trois mises en page coexistent :

- une colonne par année, le sexe étant une colonne de libellés (feuilles 1 à 5, 9, 13) ;
- trois colonnes G, F, T sous chaque année (feuilles 6 à 8, tableaux 1 à 5 du préscolaire) ;
- une seule valeur par année (indices de parité, structures et salles).

Chaque feuille est parcourue ligne par ligne : une ligne « Tableau … » ouvre un tableau,
la ligne suivante donne les colonnes de libellés et les années, une éventuelle ligne
G / F / T précise le sexe de chaque colonne. Les libellés sont reportés vers le bas
(une région vaut pour les lignes de statut qui la suivent) et reconnus par vocabulaire :
région, statut, milieu, niveau, sexe ou total. Les lignes sans libellé reconnu sont
écartées et consignées dans le journal.

Le résultat est une table longue, une valeur par ligne, avec la feuille et la ligne
d'origine dans le classeur.
"""

from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

from .geographie import CODE_NATIONAL
from .outils import Journal, lire_extrait, normaliser_nom

TABLE = "fait_base_principale"

# Indicateur, unité : l'ordre compte (les indices de parité avant les taux qu'ils portent).
_INDICATEURS = [
    ("ips du tba", "ips_tba", "indice"),
    ("ips du tbs", "ips_tbs", "indice"),
    ("ips du tap", "ips_tap", "indice"),
    ("nouveaux inscrits", "nouveaux_inscrits_cp1", "nombre"),
    ("tba", "tba", "pour cent"),
    ("tbs", "tbs", "pour cent"),
    ("achevement", "taux_achevement", "pour cent"),
    ("cep", "taux_reussite_cep", "pour cent"),
    ("structures", "structures", "nombre"),
    ("salles", "salles", "nombre"),
    ("ecoles", "ecoles", "nombre"),
    ("effectifs", "effectifs", "nombre"),
]

_STATUTS = {"PUBLIC": "public", "PRIVE": "prive", "COMMUNAUTAIRE": "communautaire"}
_MILIEUX = {"URBAIN": "urbain", "RURAL": "rural", "INDETERMINE": "indetermine"}
_SEXES = {"G": "G", "GARCONS": "G", "F": "F", "FILLES": "F", "T": "T", "TOTAL": "T"}
_CLASSES = {"CP1": "CP1", "CP2": "CP2", "CE1": "CE1", "CE2": "CE2", "CM1": "CM1", "CM2": "CM2",
            "PETITESECTION": "petite section", "MOYENNESECTION": "moyenne section",
            "GRANDESECTION": "grande section"}
_NATIONAL = {"NATIONAL", "BURKINAFASO", "TOTALGENERAL"}
# En-tête de colonne de libellés -> dimension.
_DIMENSIONS = {"REGION": "entite", "REGIONS": "entite", "STATUT": "statut", "MILIEU": "milieu",
               "NIVEAU": "classe", "SEXE": "sexe"}
_DEFAUT = {"entite_pcode": CODE_NATIONAL, "statut": "total", "milieu": "total", "classe": "total", "sexe": "T"}


def _sans_accent(texte: str) -> str:
    texte = texte.replace("’", " ").replace("'", " ")
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()


def _premiere_ligne(cellule: str) -> str:
    """Première ligne d'une cellule : certaines cellules d'en-tête portent un texte parasite à la suite."""
    return str(cellule).split("\n")[0].strip()


def annee_de_colonne(texte: str) -> str | None:
    """« 2015-2016 », « 2015/16 », « 2015-16 », « 2024/25 » ou « 2016 » (année de fin) deviennent « 2015-2016 »."""
    texte = _premiere_ligne(texte)
    m = re.fullmatch(r"(20\d{2})\s*[/-]\s*(\d{2}|20\d{2})", texte)
    if m:
        debut = int(m.group(1))
        fin = int(m.group(2)) if len(m.group(2)) == 4 else 2000 + int(m.group(2))
        return f"{debut}-{fin}" if fin == debut + 1 else None
    if re.fullmatch(r"20\d{2}", texte):
        fin = int(texte)
        return f"{fin - 1}-{fin}"
    return None


def indicateur_du_titre(titre: str) -> tuple[str, str, str]:
    """Ordre d'enseignement, indicateur et unité d'après le titre du tableau."""
    texte = _sans_accent(titre).replace("’", " ").replace("'", " ")
    ordre = "prescolaire" if "prescolaire" in texte else "primaire"
    for motif, indicateur, unite in _INDICATEURS:
        if re.search(rf"\b{motif}\b", texte):
            return ordre, indicateur, unite
    raise ValueError(f"indicateur non reconnu : {titre}")


def _valeur(texte: str) -> float:
    texte = _premiere_ligne(texte).replace(",", ".").replace(" ", "")
    return float(texte) if re.fullmatch(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?", texte) else np.nan


class _Lecteur:
    """Reconnaît les libellés de lignes : régions, national, statut, milieu, niveau, sexe, totaux."""

    def __init__(self, alias: pd.DataFrame):
        regions = alias[alias["niveau"] == "region_ancienne"]
        self.regions = dict(zip(regions["nom_normalise"], regions["pcode"]))
        self.regions.setdefault("HAUTBASSINS", self.regions.get("HAUTSBASSINS"))

    def reconnaitre(self, libelle: str, dimension: str) -> dict | None:
        """Dimensions fixées par un libellé ; None si le libellé n'est pas reconnu.

        « Total X » fixe X et laisse les autres dimensions à leur valeur totale ;
        « Total » seul vaut total de la dimension de la colonne.
        """
        cle = normaliser_nom(libelle)
        if cle in _NATIONAL:
            return {"entite_pcode": CODE_NATIONAL}
        if cle.startswith("TOTAL") and cle != "TOTAL":
            return self.reconnaitre(libelle.strip()[5:], dimension)
        if cle == "TOTAL" and dimension != "sexe":
            return {"entite_pcode" if dimension == "entite" else dimension:
                    CODE_NATIONAL if dimension == "entite" else "total"}
        if cle in self.regions and self.regions[cle]:
            return {"entite_pcode": self.regions[cle]}
        if cle in _STATUTS:
            return {"statut": _STATUTS[cle]}
        if cle in _MILIEUX:
            return {"milieu": _MILIEUX[cle]}
        if cle in _CLASSES:
            return {"classe": _CLASSES[cle]}
        if cle in _SEXES:
            return {"sexe": _SEXES[cle]}
        return None


def _colonnes(feuille: pd.DataFrame) -> list[str]:
    return sorted((c for c in feuille.columns if re.fullmatch(r"col\d+", c)), key=lambda c: int(c[3:]))


def _lire_tableau(lignes: pd.DataFrame, colonnes: list[str], lecteur: _Lecteur, feuille: str, numero: int,
                  journal: Journal) -> list[dict]:
    titre = _premiere_ligne(lignes.iloc[0]["col1"])
    ordre, indicateur, unite = indicateur_du_titre(titre)
    entete = lignes.iloc[1]

    # Colonnes de libellés (avant la première année) et colonnes d'années.
    libelles, annees = [], {}
    for colonne in colonnes:
        texte = _premiere_ligne(entete[colonne])
        annee = annee_de_colonne(texte)
        if annee:
            annees[colonne] = annee
        elif not annees and texte:
            libelles.append((colonne, _DIMENSIONS.get(normaliser_nom(texte), "entite")))

    # Ligne G / F / T éventuelle : chaque colonne prend l'année de la dernière année d'en-tête à sa gauche.
    debut_donnees, sexe_colonne = 2, {}
    sous_entete = lignes.iloc[2] if len(lignes) > 2 else None
    if sous_entete is not None and {_premiere_ligne(sous_entete[c]) for c in colonnes} - {""} <= {"G", "F", "T"} \
            and any(_premiere_ligne(sous_entete[c]) for c in colonnes):
        debut_donnees, annee_courante, groupes = 3, None, {}
        for colonne in colonnes:
            annee_courante = annees.get(colonne, annee_courante)
            sexe = _premiere_ligne(sous_entete[colonne])
            if sexe and annee_courante:
                groupes[colonne] = annee_courante
                sexe_colonne[colonne] = sexe
        annees = groupes

    resultats, courant = [], [None] * len(libelles)
    for _, ligne in lignes.iloc[debut_donnees:].iterrows():
        valeurs = {c: _valeur(ligne[c]) for c in annees}
        if all(np.isnan(v) for v in valeurs.values()):
            continue
        # Une ligne de données porte au moins un libellé (cellules isolées en bas de feuille écartées).
        if not any(_premiere_ligne(ligne[c]) for c, _d in libelles):
            journal.noter(TABLE, "ligne écartée", "valeur isolée sans libellé", source=feuille,
                          ligne=str(ligne["ligne"]), avant=" ".join(f"{v:g}" for v in valeurs.values() if not np.isnan(v)))
            continue
        # Report des libellés vers le bas : un libellé efface ceux des colonnes plus à droite.
        for i, (colonne, _dimension) in enumerate(libelles):
            texte = _premiere_ligne(ligne[colonne])
            if texte:
                courant[i] = texte
                courant[i + 1:] = [None] * (len(libelles) - i - 1)
        dimensions, reconnu = dict(_DEFAUT), True
        for texte, (_colonne, dimension) in zip(courant, libelles):
            if texte is None:
                continue
            fixe = lecteur.reconnaitre(texte, dimension)
            if fixe is None:
                reconnu = False
                break
            dimensions.update(fixe)
        if not reconnu:
            journal.noter(TABLE, "ligne écartée", "libellé non reconnu", source=feuille,
                          ligne=str(ligne["ligne"]), avant=" | ".join(t for t in courant if t)[:120])
            continue
        for colonne, valeur in valeurs.items():
            if np.isnan(valeur):
                continue
            resultats.append({
                "tableau": f"{feuille} T{numero}", "ordre": ordre, "indicateur": indicateur, "unite": unite,
                **dimensions, "sexe": sexe_colonne.get(colonne, dimensions["sexe"]),
                "annee_scolaire": annees[colonne], "valeur": valeur,
                "feuille": feuille, "ligne": int(ligne["ligne"]), "titre": titre,
            })
    return resultats


def lire_base_principale(alias: pd.DataFrame, journal: Journal) -> pd.DataFrame:
    """Tous les tableaux de la base principale en une table longue."""
    brut = lire_extrait("dgess_base_principale")
    lecteur = _Lecteur(alias)
    lignes = []
    for feuille, contenu in brut.groupby("feuille", sort=False):
        contenu = contenu.reset_index(drop=True)
        colonnes = _colonnes(contenu)
        titres = contenu.index[contenu["col1"].str.match(r"(?i)^\s*tableau\s*\d+")].tolist()
        for rang, debut in enumerate(titres):
            fin = titres[rang + 1] if rang + 1 < len(titres) else len(contenu)
            numero = int(re.search(r"\d+", contenu.loc[debut, "col1"]).group())
            lignes += _lire_tableau(contenu.iloc[debut:fin], colonnes, lecteur, feuille, numero, journal)
    table = pd.DataFrame(lignes)
    table["niveau_geo"] = np.where(table["entite_pcode"] == CODE_NATIONAL, "pays", "region_ancienne")
    table["source_fichier"] = brut["source_fichier"].iloc[0]
    colonnes = ["tableau", "ordre", "indicateur", "unite", "niveau_geo", "entite_pcode", "statut", "milieu",
                "classe", "sexe", "annee_scolaire", "valeur", "source_fichier", "feuille", "ligne", "titre"]
    return table[colonnes].sort_values(["tableau", "entite_pcode", "statut", "milieu", "classe", "sexe",
                                        "annee_scolaire"]).reset_index(drop=True)


# Contrôles ------------------------------------------------------------------------------------------

_CLE = ["tableau", "statut", "milieu", "classe", "sexe", "entite_pcode", "annee_scolaire"]


def controle_unicite(table: pd.DataFrame) -> pd.DataFrame:
    doublons = table[table.duplicated(_CLE, keep=False)]
    return pd.DataFrame([{"lignes": len(table), "doublons": len(doublons), "conforme": doublons.empty}])


def controle_sommes(table: pd.DataFrame, tolerance: float = 0.5) -> pd.DataFrame:
    """Pour les comptages : somme des régions = national, G + F = T, somme des statuts, milieux, niveaux = total."""
    comptes = table[table["unite"] == "nombre"]
    lignes = []
    for dimension, total in [("entite_pcode", CODE_NATIONAL), ("sexe", "T"), ("statut", "total"),
                             ("milieu", "total"), ("classe", "total")]:
        autres = [c for c in _CLE if c != dimension]
        parties = comptes[comptes[dimension] != total].groupby(autres)["valeur"].agg(["sum", "count"])
        totaux = comptes[comptes[dimension] == total].set_index(autres)["valeur"]
        commun = parties[parties["count"] > 1].join(totaux.rename("total"), how="inner")
        if commun.empty:
            continue
        commun["ecart"] = commun["sum"] - commun["total"]
        for tableau, groupe in commun.reset_index().groupby("tableau"):
            ecarts = groupe[groupe["ecart"].abs() > tolerance]
            lignes.append({"tableau": tableau, "dimension": dimension, "sommes_verifiees": len(groupe),
                           "sommes_en_ecart": len(ecarts),
                           "annees_en_ecart": ", ".join(sorted(ecarts["annee_scolaire"].unique())),
                           "conforme": ecarts.empty})
    return pd.DataFrame(lignes)


def signaler_sauts(table: pd.DataFrame, journal: Journal, facteur: float = 2.5, minimum: float = 20) -> pd.DataFrame:
    """Comptages qui varient d'un facteur supérieur à 2,5 d'une année à l'autre : signalés, non corrigés."""
    comptes = table[(table["unite"] == "nombre")].sort_values(_CLE)
    autres = [c for c in _CLE if c != "annee_scolaire"]
    comptes = comptes.assign(precedent=comptes.groupby(autres)["valeur"].shift())
    rapport = comptes["valeur"] / comptes["precedent"]
    sauts = comptes[(comptes[["valeur", "precedent"]].max(axis=1) >= minimum)
                    & ((rapport > facteur) | (rapport < 1 / facteur))]
    for s in sauts.itertuples():
        journal.noter(TABLE, "signalement", f"variation brutale d'une année à l'autre (facteur > {facteur})",
                      source=s.feuille, ligne=str(s.ligne),
                      avant=f"{s.tableau} {s.entite_pcode} {s.statut} {s.annee_scolaire} : {s.precedent:g}",
                      apres=f"{s.valeur:g}")
    return sauts[_CLE + ["precedent", "valeur", "feuille", "ligne"]].reset_index(drop=True)
