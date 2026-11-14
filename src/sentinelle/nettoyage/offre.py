"""Offre scolaire par province : tableau I.1 des annuaires (II.1 en 2017-2018).

Pour chaque province et chaque statut (public, privé, total) : écoles, salles de
classe, groupes pédagogiques, maîtres chargés de cours, élèves, et le ratio
élèves par maître publié. Une ligne contient le nom de la province (sur la ligne
du statut public), le statut et six valeurs ; les lignes « Total Région » sont
rattachées à la région du bloc en cours.
"""

from __future__ import annotations

import pandas as pd

from .dgess import Identification, _trier
from .outils import Journal, cellules, colonnes_cellules, en_nombre, est_nombre, lire_extrait, normaliser_nom

VARIABLES = ["ecoles", "salles", "groupes_pedagogiques", "maitres", "eleves", "eleves_par_maitre_publie"]
STATUTS = {"PUBLIC": "public", "PRIVE": "prive", "TOTAL": "total"}


def lire_offre(identifier: Identification, journal: Journal) -> pd.DataFrame:
    table = "fait_offre_province"
    brut = _trier(lire_extrait("dgess_principaux_chiffres_province"))
    colonnes = colonnes_cellules(brut)
    lignes = []
    for fichier, bloc in brut.groupby("source_fichier", sort=False):
        edition = bloc["source_periode"].iloc[0]
        entite, region = None, None
        for _, row in bloc.iterrows():
            cel = cellules(row, colonnes)
            textes = [c for c in cel if not est_nombre(c)]
            nombres = [en_nombre(c) for c in cel if est_nombre(c)]
            statut = next((STATUTS[normaliser_nom(t)] for t in textes if normaliser_nom(t) in STATUTS), None)
            noms = [t for t in textes if normaliser_nom(t) not in STATUTS]

            if noms:
                nom = " ".join(noms)
                if normaliser_nom(nom).startswith("TOTALREGION"):
                    entite = region
                elif (trouve := identifier(nom)) is not None:
                    entite = (*trouve, nom)
                    if trouve[1] == "region_ancienne":
                        region = entite
                elif nombres:
                    journal.noter(table, "ligne ignorée", "nom absent de la table des alias", source=fichier,
                                  page=row["page"], ligne=row["ligne"], avant=" | ".join(cel))
                    entite = None
            if statut is None or entite is None or not nombres:
                continue
            if len(nombres) != 6:
                journal.noter(table, "ligne ignorée", f"{len(nombres)} valeurs au lieu de 6", source=fichier,
                              page=row["page"], ligne=row["ligne"], avant=" | ".join(cel))
                continue
            code, niveau_geo, nom = entite
            lignes.append({"annee_scolaire": edition, "entite_pcode": code, "niveau_geo": niveau_geo,
                           "statut": statut, **dict(zip(VARIABLES, nombres)), "source_fichier": fichier,
                           "page": row["page"]})
    offre = pd.DataFrame(lignes).drop_duplicates(["annee_scolaire", "entite_pcode", "statut"])
    offre["eleves_par_maitre"] = (offre["eleves"] / offre["maitres"]).round(2)
    offre["eleves_par_salle"] = (offre["eleves"] / offre["salles"]).round(2)
    return offre
