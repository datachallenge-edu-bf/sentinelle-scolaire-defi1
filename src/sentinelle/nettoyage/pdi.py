"""Remise en forme des situations de personnes déplacées internes (SP/CONASUR, via HDX).

Deux formats coexistent :

- fichiers détaillés : une ligne par site d'accueil, avec les P-codes (ancien
  découpage) de la région, de la province et de la commune ;
- fichiers de synthèse : une ligne par commune, sans P-code.

Le P-code est utilisé quand il existe, sinon le nom de la commune, rapproché du
référentiel (avec la province pour lever les homonymies). Le résultat donne, par
date de situation et par commune, le nombre total de déplacés et d'enfants
déplacés. Les tableaux croisés et récapitulatifs, sans colonne commune, sont écartés.
"""

from __future__ import annotations

import re
from difflib import get_close_matches

import pandas as pd

from .outils import Journal, en_nombre, lire_extrait, normaliser_nom

_TOTAL = re.compile(r"total\s*individus|nombre\s*total\s*de\s*pdi|total\s*pdis?", re.IGNORECASE)
_ENFANTS = re.compile(r"^total\s*enfants", re.IGNORECASE)
_COMMUNE = re.compile(r"^communes?(\s*\(destination\))?$|commune\s*d.accueil", re.IGNORECASE)
_PROVINCE = re.compile(r"^provinces?(\s*\(destination\))?$", re.IGNORECASE)
_PCODE3 = re.compile(r"admin\s*3\s*p?code|^admin3", re.IGNORECASE)
_DATE = re.compile(r"^date", re.IGNORECASE)

# Communes dont le nom dans les fichiers CONASUR diffère trop de COD-AB pour un rapprochement automatique.
# Les arrondissements de Ouagadougou relèvent de la commune de Ouagadougou.
ALIAS_COMMUNES = {
    "BANH": "BF540101",          # Bahn
    "COALLA": "BF580103",        # Koala
    "GOURCY": "BF540403",        # Goursi
    "TOEGHIN": "BF550205",       # Toeguen
    "GOUNGHIN": "BF480304",      # Gounguen
    "SIBI": "BF620109",          # Siby
    "FADA": "BF630103",          # Fada-Ngourma
    "FADANGOURMA": "BF630103",
}
_ARRONDISSEMENT_OUAGADOUGOU = "BF130004"


def _index_communes(communes: pd.DataFrame) -> tuple[dict, dict, set]:
    par_nom: dict[str, list[tuple[str, str]]] = {}
    for r in communes.itertuples():
        par_nom.setdefault(normaliser_nom(r.commune_nom), []).append((r.commune_pcode, r.province_ancienne_pcode))
    ancien_vers_nouveau = dict(zip(communes["commune_ancienne_pcode"], communes["commune_pcode"]))
    actuels = set(communes["commune_pcode"])
    return par_nom, ancien_vers_nouveau, actuels


def _rapprocher(nom: str, province: str, par_nom: dict, alias_provinces: dict[str, str]) -> str | None:
    """Commune dont l'orthographe est la plus proche, dans la même province si elle est connue."""
    code_province = alias_provinces.get(normaliser_nom(province))
    noms = [n for n, lieux in par_nom.items()
            if code_province is None or any(c[1] == code_province for c in lieux)]
    proche = get_close_matches(normaliser_nom(nom), noms, n=1, cutoff=0.8)
    if not proche:
        return None
    lieux = [c for c in par_nom[proche[0]] if code_province is None or c[1] == code_province]
    return lieux[0][0] if len(lieux) == 1 else None


def lire_pdi(communes: pd.DataFrame, alias_provinces: dict[str, str], journal: Journal) -> pd.DataFrame:
    """Déplacés internes par commune (P-code actuel) et par date de situation."""
    table = "fait_pdi_commune"
    brut = lire_extrait("pdi_conasur_commune")
    colonnes = [c for c in brut.columns if re.fullmatch(r"col\d+", c)]
    par_nom, ancien_vers_nouveau, actuels = _index_communes(communes)
    resultats = []

    for fichier, bloc in brut.groupby("source_csv_pack", sort=False):
        bloc = bloc.reset_index(drop=True)
        entete = next((i for i in range(min(15, len(bloc)))
                       if any(_COMMUNE.search(bloc.at[i, c].strip()) for c in colonnes)), None)
        if entete is None:
            journal.noter(table, "fichier écarté", "pas de colonne commune : tableau croisé ou récapitulatif",
                          source=fichier)
            continue
        noms = {c: bloc.at[entete, c].strip() for c in colonnes}
        trouver = lambda motif: next((c for c, n in noms.items() if n and motif.search(n)), None)  # noqa: E731
        c_commune, c_province, c_total = trouver(_COMMUNE), trouver(_PROVINCE), trouver(_TOTAL)
        c_enfants, c_pcode, c_date = trouver(_ENFANTS), trouver(_PCODE3), trouver(_DATE)
        if c_total is None:
            journal.noter(table, "fichier écarté", "pas de colonne de total des déplacés", source=fichier)
            continue

        donnees = bloc.iloc[entete + 1:]
        donnees = donnees[~donnees[c_commune].str.startswith("#")]  # ligne d'étiquettes HXL
        periode = bloc["source_periode"].iloc[0]
        non_rapproches, approches = set(), set()

        for _, row in donnees.iterrows():
            total = en_nombre(row[c_total])
            if pd.isna(total):
                continue
            code = None
            if c_pcode and (p := row[c_pcode].strip()):
                code = p if p in actuels else ancien_vers_nouveau.get(p)
            nom = row[c_commune].strip()
            cle = normaliser_nom(nom)
            if code is None and (cle in ALIAS_COMMUNES or cle.startswith("ARRONDISSEMENT")):
                code = ALIAS_COMMUNES.get(cle, _ARRONDISSEMENT_OUAGADOUGOU)
            if code is None and nom:
                candidats = par_nom.get(normaliser_nom(nom), [])
                if len(candidats) > 1 and c_province:
                    province = alias_provinces.get(normaliser_nom(row[c_province]))
                    candidats = [c for c in candidats if c[1] == province] or candidats
                code = candidats[0][0] if len(candidats) == 1 else None
                if code is None and not candidats:
                    code = _rapprocher(nom, row[c_province] if c_province else "", par_nom, alias_provinces)
                    if code is not None:
                        approches.add(f"{nom} -> {code}")
                if code is None:
                    non_rapproches.add(nom)
            if code is None:
                continue
            date = row[c_date].strip()[:10] if c_date and row[c_date].strip() else periode
            resultats.append({
                "date_situation": date,
                "commune_pcode": code,
                "pdi_total": total,
                "pdi_enfants": en_nombre(row[c_enfants]) if c_enfants else float("nan"),
                "source_csv_pack": fichier,
            })

        for correspondance in sorted(approches):
            journal.noter(table, "rapprochement approché", "orthographe voisine dans la même province",
                          source=fichier, avant=correspondance.split(" -> ")[0], apres=correspondance.split(" -> ")[1])
        for nom in sorted(non_rapproches):
            journal.noter(table, "commune non rapprochée", "nom de commune absent ou ambigu dans le référentiel",
                          source=fichier, avant=nom)

    detail = pd.DataFrame(resultats)
    # Plusieurs fichiers pour une même date (version brute et version nettoyée) : la version
    # « après nettoyage » est préférée, sinon la première.
    detail["priorite"] = (~detail["source_csv_pack"].str.contains("nettoyage")).astype(int)
    retenu = detail.sort_values("priorite").groupby("date_situation")["source_csv_pack"].first()
    for date, groupe in detail.groupby("date_situation"):
        for autre in sorted(set(groupe["source_csv_pack"]) - {retenu[date]}):
            journal.noter(table, "fichier doublon écarté", f"autre version de la situation au {date}",
                          source=autre, apres=retenu[date])
    detail = detail[detail["source_csv_pack"] == detail["date_situation"].map(retenu)]

    return (detail.groupby(["date_situation", "commune_pcode"], as_index=False)
            .agg(pdi_total=("pdi_total", "sum"), pdi_enfants=("pdi_enfants", lambda v: v.sum(min_count=1)),
                 source_csv_pack=("source_csv_pack", "first"))
            .sort_values(["date_situation", "commune_pcode"]))
