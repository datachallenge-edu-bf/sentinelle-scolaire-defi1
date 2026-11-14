"""Remise en forme des tableaux provinciaux des annuaires DGESS du primaire.

Deux tableaux sont lus pour chacune des huit éditions (2017-2018 à 2024-2025) :

- I.8 (II.7 en 2017-2018) : taux de promotion, redoublement et abandon par
  province, classe et sexe. Chaque entité occupe trois lignes (TX Prom, TX Red,
  TX Aban) ; son nom figure sur l'une d'elles, parfois coupé sur deux lignes.
  L'édition 2017-2018 ne publie pas de totaux régionaux, seulement les provinces
  et le total national.
- VIII.3 (IX.3 en 2017-2018) : historique des effectifs et des redoublants par
  province, classe et sexe, sur une dizaine d'années.

Le résultat est en format long : une valeur par ligne, avec son origine.
"""

from __future__ import annotations

import re

import pandas as pd

from .outils import Journal, annee_scolaire, cellules, colonnes_cellules, en_nombre, est_nombre, lire_extrait, normaliser_nom

NIVEAUX = ["CP1", "CP2", "CE1", "CE2", "CM1", "CM2"]
SEXES = ["G", "F", "T"]
SEXES_LIGNE = {"GARCONS": "G", "FILLES": "F", "TOTAL": "T"}

_LIBELLE_FLUX = re.compile(r"^T[Xx]\.?\s*(Prom|Red|Aban)", re.IGNORECASE)
_INDICATEURS = {"prom": "promotion", "red": "redoublement", "aban": "abandon"}
_ENTETE = re.compile(
    r"ann[ée]e\s+scolaire|principaux\s+chiffres|LESPRINCIPAUX|TAUX DE PROMOTION|HISTORIQUE|^BF/|^(?:CP1|G|Total)$",
    re.IGNORECASE,
)


class Identification:
    """Reconnaît une entité (province, région, pays) de l'ancien découpage à partir de son nom."""

    def __init__(self, alias: pd.DataFrame):
        self._table = {r.nom_normalise: (r.pcode, r.niveau) for r in alias.itertuples()}

    def __call__(self, nom: str) -> tuple[str, str] | None:
        return self._table.get(normaliser_nom(nom))


def _trier(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(
        _page=pd.to_numeric(df["page"], errors="coerce"),
        _ligne=pd.to_numeric(df["ligne"], errors="coerce"),
    ).sort_values(["source_fichier", "_page", "_ligne"])


def lire_flux(identifier: Identification, journal: Journal) -> pd.DataFrame:
    """Taux de promotion, de redoublement et d'abandon publiés, en format long."""
    table = "fait_flux_province"
    brut = _trier(lire_extrait("dgess_flux_province"))
    colonnes = colonnes_cellules(brut)
    lignes: list[dict] = []

    for fichier, bloc in brut.groupby("source_fichier", sort=False):
        edition = bloc["source_periode"].iloc[0]
        groupe: dict | None = None
        titre_bloc = ""

        for _, row in bloc.iterrows():
            cel = _separer_libelle(cellules(row, colonnes))
            if not cel:
                continue
            position = next((i for i, c in enumerate(cel) if _LIBELLE_FLUX.match(c)), None)

            if position is None:
                texte = " ".join(c for c in cel if not est_nombre(c))
                if not texte or _ENTETE.search(texte) or cel[0] in NIVEAUX or cel[0] in SEXES:
                    continue
                if groupe is not None:
                    groupe["noms"].append(texte)
                else:
                    titre_bloc = texte
                continue

            indicateur = _INDICATEURS[_LIBELLE_FLUX.match(cel[position]).group(1).lower()]
            noms = [c for c in cel[:position] if not est_nombre(c)]
            valeurs = [en_nombre(c) for c in cel[position + 1:]]

            if indicateur == "promotion":
                groupe = {"noms": noms, "valeurs": {}, "page": row["page"], "ligne": row["ligne"]}
            elif groupe is None:
                journal.noter(table, "ligne ignorée", f"ligne {indicateur} sans ligne de promotion qui la précède",
                              source=fichier, page=row["page"], ligne=row["ligne"], avant=" | ".join(cel))
                continue
            else:
                groupe["noms"].extend(noms)
            groupe["valeurs"][indicateur] = valeurs

            if indicateur == "abandon":
                lignes.extend(_terminer_groupe(groupe, titre_bloc, edition, fichier, identifier, journal, table))
                groupe = None

    return pd.DataFrame(lignes)


def _separer_libelle(cel: list[str]) -> list[str]:
    """Sépare un nom collé au libellé dans la même cellule : « PLATEAU CENTRAL TX Red »."""
    resultat = []
    for c in cel:
        m = re.search(r"\s(T[Xx]\.?\s*(?:Prom|Red|Aban))\s*$", c, flags=re.IGNORECASE)
        if m and c[:m.start()].strip():
            resultat.extend([c[:m.start()].strip(), m.group(1)])
        else:
            resultat.append(c)
    return resultat


def _terminer_groupe(groupe: dict, titre_bloc: str, edition: str, fichier: str,
                     identifier: Identification, journal: Journal, table: str) -> list[dict]:
    nom = " ".join(groupe["noms"]).strip() or titre_bloc
    entite = identifier(nom) or identifier(f"{titre_bloc} {nom}")
    if entite is None:
        journal.noter(table, "entité non reconnue", "nom absent de la table des alias",
                      source=fichier, page=groupe["page"], ligne=groupe["ligne"], avant=nom)
        return []

    code, niveau_geo = entite
    lignes = []
    for indicateur, valeurs in groupe["valeurs"].items():
        if len(valeurs) % 3 or len(valeurs) > 18:
            journal.noter(table, "ligne ignorée", f"{len(valeurs)} valeurs au lieu de 15 ou 18",
                          source=fichier, page=groupe["page"], ligne=groupe["ligne"], avant=f"{nom} {indicateur}")
            continue
        # Promotion et abandon couvrent CP1 à CM1 ; le redoublement couvre CP1 à CM2.
        for k, valeur in enumerate(valeurs):
            lignes.append({
                "annee_publication": edition,
                "entite_pcode": code,
                "niveau_geo": niveau_geo,
                "nom_source": nom,
                "niveau": NIVEAUX[k // 3],
                "sexe": SEXES[k % 3],
                "indicateur": indicateur,
                "valeur_pct": valeur,
                "source_fichier": fichier,
                "page": groupe["page"],
            })
    return lignes


def annee_decalee(annee: str, recul: int) -> str:
    """Année scolaire reculée de « recul » ans : (« 2024-2025 », 2) donne « 2022-2023 »."""
    debut = int(annee[:4]) - recul
    return f"{debut}-{debut + 1}"


def _annee_valide(etiquette: str | None, edition: str) -> bool:
    if etiquette is None:
        return False
    debut, fin = int(etiquette[:4]), int(etiquette[5:])
    return fin == debut + 1 and etiquette <= edition


def _dater_bloc(etiquettes: list[str | None], edition: str) -> tuple[list[str], list[str]]:
    """Fixe l'année de chaque groupe de trois lignes d'un bloc.

    L'étiquette lue dans le PDF fait foi quand elle est valide et non répétée.
    Sinon l'année se déduit de l'étiquette voisine : la suivante plus un an, ou à
    défaut la précédente moins un an, ou l'année de l'édition en tête de bloc.
    Renvoie les années et, pour chacune, le motif d'une éventuelle correction.
    """
    n = len(etiquettes)
    fiables = [
        _annee_valide(e, edition) and (i + 1 >= n or e != etiquettes[i + 1])
        for i, e in enumerate(etiquettes)
    ]
    annees: list[str | None] = [e if f else None for e, f in zip(etiquettes, fiables)]

    for i in range(n - 2, -1, -1):
        if annees[i] is None and annees[i + 1] is not None:
            annees[i] = annee_decalee(annees[i + 1], -1)
    for i in range(n):
        if annees[i] is None:
            annees[i] = annee_decalee(annees[i - 1], 1) if i > 0 else edition

    motifs = []
    for e, f in zip(etiquettes, fiables):
        if f:
            motifs.append("")
        elif e is None:
            motifs.append("étiquette d'année absente ou illisible : déduite des années voisines")
        elif not _annee_valide(e, edition):
            motifs.append("étiquette d'année invalide : déduite des années voisines")
        else:
            motifs.append("étiquette d'année répétée : déduite des années voisines")
    return annees, motifs


def lire_effectifs(identifier: Identification, journal: Journal) -> pd.DataFrame:
    """Effectifs et redoublants par entité, année, classe et sexe, pour chaque édition.

    Chaque bloc donne, pour une entité, les années de la plus récente à la plus
    ancienne, trois lignes par année (garçons, filles, total). Un bloc est d'abord
    lu en entier, puis ses années sont fixées par ``_dater_bloc``.
    """
    table = "fait_effectifs_province"
    brut = _trier(lire_extrait("dgess_effectifs_redoublants_province"))
    colonnes = colonnes_cellules(brut)
    lignes: list[dict] = []

    for fichier, bloc in brut.groupby("source_fichier", sort=False):
        edition = bloc["source_periode"].iloc[0]
        entite: tuple[str, str, str] | None = None
        groupes: list[dict] = []
        etiquette_attente: str | None = None
        nouvelle_annee = False

        def vider() -> None:
            if entite is None or not groupes:
                return
            code, niveau_geo, nom = entite
            # Un groupe imprimé deux fois de suite (même étiquette, mêmes valeurs) est un doublon du PDF.
            uniques = []
            for groupe in groupes:
                precedent = uniques[-1] if uniques else None
                if (precedent is not None and groupe["etiquette"] == precedent["etiquette"]
                        and groupe["lignes"] == precedent["lignes"]):
                    journal.noter(table, "doublon retiré", "groupe d'année imprimé deux fois dans le PDF",
                                  source=fichier, page=groupe["page"], ligne=groupe["ligne"],
                                  avant=f"{nom} {groupe['etiquette']}")
                    continue
                uniques.append(groupe)
            groupes[:] = uniques
            annees, motifs = _dater_bloc([g["etiquette"] for g in groupes], edition)
            for groupe, annee, motif in zip(groupes, annees, motifs):
                if motif:
                    journal.noter(table, "année déduite", motif, source=fichier, page=groupe["page"],
                                  ligne=groupe["ligne"], avant=f"{nom} {groupe['etiquette'] or ''}".strip(),
                                  apres=annee)
                for sexe, contenu in groupe["lignes"].items():
                    if contenu is None:  # ligne écartée, déjà consignée au journal
                        continue
                    valeurs, page = contenu
                    for k, niveau in enumerate(NIVEAUX + ["Total"]):
                        lignes.append({
                            "annee_publication": edition,
                            "annee_scolaire": annee,
                            "entite_pcode": code,
                            "niveau_geo": niveau_geo,
                            "nom_source": nom,
                            "niveau": niveau,
                            "sexe": sexe,
                            "effectif": valeurs[2 * k],
                            "redoublants": valeurs[2 * k + 1],
                            "source_fichier": fichier,
                            "page": page,
                        })

        for _, row in bloc.iterrows():
            cel = cellules(row, colonnes)
            if not cel:
                continue

            if len(cel) == 1:
                texte = cel[0]
                if (a := annee_scolaire(texte)) is not None or re.fullmatch(r"\d{4}\s*/\s*\d{4}", texte):
                    etiquette_attente = a if a is not None else texte.replace(" ", "").replace("/", "-")
                    nouvelle_annee = True
                elif re.fullmatch(r"\d{8,9}", texte):
                    etiquette_attente, nouvelle_annee = None, True
                elif est_nombre(texte) or _ENTETE.search(texte):
                    continue
                elif (trouve := identifier(texte)) is not None:
                    vider()
                    entite, groupes, etiquette_attente, nouvelle_annee = (*trouve, texte), [], None, False
                else:
                    journal.noter(table, "entité non reconnue", "nom absent de la table des alias",
                                  source=fichier, page=row["page"], ligne=row["ligne"], avant=texte)
                    vider()
                    entite, groupes = None, []
                continue

            if len(cel) < 2 or not est_nombre(cel[1]):
                continue
            libelle = normaliser_nom(cel[0])
            sexe = SEXES_LIGNE.get(libelle)
            if sexe is None and not libelle.startswith("SOMME"):
                continue
            if entite is None:
                journal.noter(table, "ligne ignorée", "ligne de valeurs sans entité identifiée",
                              source=fichier, page=row["page"], ligne=row["ligne"], avant=" | ".join(cel))
                continue

            courant = groupes[-1] if groupes else None
            if (courant is None or nouvelle_annee or (sexe is not None and sexe in courant["lignes"])
                    or len(courant["lignes"]) == 3):
                courant = {"etiquette": etiquette_attente, "lignes": {}, "page": row["page"], "ligne": row["ligne"]}
                groupes.append(courant)
                etiquette_attente, nouvelle_annee = None, False

            if sexe is None:
                # Libellé « Somme de » : le sexe se déduit de la position dans le groupe de trois lignes.
                sexe = SEXES[len(courant["lignes"])]
                journal.noter(table, "libellé corrigé", "libellé « Somme de » : sexe déduit de la position",
                              source=fichier, page=row["page"], ligne=row["ligne"], avant=cel[0], apres=sexe)

            valeurs = [en_nombre(c) for c in cel[1:]]
            if len(valeurs) != 14:
                journal.noter(table, "ligne ignorée", f"{len(valeurs)} valeurs au lieu de 14",
                              source=fichier, page=row["page"], ligne=row["ligne"], avant=" | ".join(cel))
                courant["lignes"].setdefault(sexe, None)
                continue
            courant["lignes"][sexe] = (valeurs, row["page"])

        vider()

    return pd.DataFrame(lignes)
