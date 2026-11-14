"""Remise en forme des rapports mensuels du ST-ESU (éducation en situation d'urgence).

Les tableaux « Situation des établissements fermés » et « Situation des
établissements rouverts » donnent, par ordre d'enseignement puis par région et
province : le nombre d'établissements, les élèves concernés (filles, garçons,
total) et les enseignants concernés (femmes, hommes, total).

Seul le primaire est retenu. La mise en page varie d'un mois à l'autre et la
plupart des rapports sont lus par reconnaissance de caractères : chaque ligne
est contrôlée (filles + garçons = total, femmes + hommes = total) et la somme
des provinces est comparée à la ligne « TOTAL PRIMAIRE » du rapport.
"""

from __future__ import annotations

import re

import pandas as pd

from .dgess import Identification
from .outils import Journal, cellules, colonnes_cellules, en_nombre, lire_extrait, normaliser_nom

_TITRE = re.compile(r"Tableau\s*\d+\s*:?\s*(?:Situation|R[ée]partition)\s+des\s+(?:structures\s+)?"
                    r"([ée]tablissements|structures)?\s*(?:scolaires\s+)?(ferm|rouvert|r[ée]ouvert|d[ée]localis|accueil)",
                    re.IGNORECASE)
_SECTION = {
    "PRESCOLAIRE": "prescolaire",
    "PRIMAIRE": "primaire",
    "POSTPRIMAIRE": "post_primaire",
    "POSTPRIMAIREETSECONDAIRE": "post_primaire",
    "SECONDAIRE": "secondaire",
    "ENSEIGNEMENTSUPERIEUR": "superieur",
}
_TYPES = {"ferm": "fermes", "rouvert": "rouverts", "reouvert": "rouverts", "réouvert": "rouverts",
          "delocalis": "delocalises", "délocalis": "delocalises", "accueil": "accueil"}
_RETENUS = {"fermes", "rouverts"}
_NON_DISPONIBLE = {"NP", "ND", "-", "--"}


def _valeur(texte: str) -> float:
    return float("nan") if texte.strip().upper() in _NON_DISPONIBLE else en_nombre(texte)


def lire_esu(identifier: Identification, journal: Journal) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Écoles primaires fermées et rouvertes par province et par rapport mensuel.

    Renvoie la table des lignes provinciales et la table des totaux publiés
    (ligne « TOTAL PRIMAIRE ») qui sert au contrôle.
    """
    table = "fait_esu_province"
    brut = lire_extrait("esu_rapports_mensuels")
    brut = brut.assign(_p=pd.to_numeric(brut["page"]), _l=pd.to_numeric(brut["ligne"])).sort_values(
        ["source_fichier", "_p", "_l"])
    colonnes = colonnes_cellules(brut)
    lignes, totaux = [], []

    for fichier, bloc in brut.groupby("source_fichier", sort=False):
        mois = bloc["source_periode"].iloc[0]
        methode = bloc["methode"].iloc[0] if "methode" in bloc else ""
        type_tableau, ordre = None, None

        for _, row in bloc.iterrows():
            cel = cellules(row, colonnes)
            if not cel:
                continue
            texte = " ".join(cel)

            if (m := _TITRE.search(texte)) is not None:
                type_tableau = _TYPES.get(m.group(2).lower().replace("é", "e"), _TYPES.get(m.group(2).lower()))
                ordre = None
                continue
            cle = normaliser_nom(texte)
            if cle in _SECTION:
                ordre = _SECTION[cle]
                continue
            if type_tableau not in _RETENUS or ordre != "primaire":
                continue

            if cle.startswith("TOTALPRIMAIRE"):
                valeurs = [_valeur(c) for c in cel if c.strip() and (c.strip().upper() in _NON_DISPONIBLE or re.search(r"\d", c))]
                totaux.append({"source_fichier": fichier, "mois": mois, "type": type_tableau,
                               "etablissements_publie": valeurs[0] if valeurs else float("nan"),
                               "eleves_total_publie": valeurs[3] if len(valeurs) > 3 else float("nan")})
                ordre = None
                continue
            if cle.startswith("TOTAL"):
                continue

            # Une ligne provinciale : un nom de province suivi de sept valeurs.
            position = next((i for i, c in enumerate(cel)
                             if (e := identifier(c)) is not None and e[1] == "province_ancienne"), None)
            if position is None:
                continue
            valeurs = [_valeur(c) for c in cel[position + 1:]]
            if len(valeurs) != 7:
                journal.noter(table, "ligne ignorée", f"{len(valeurs)} valeurs au lieu de 7",
                              source=fichier, page=row["page"], ligne=row["ligne"], avant=texte)
                continue

            code = identifier(cel[position])[0]
            etab, filles, garcons, eleves, femmes, hommes, enseignants = valeurs
            controle_eleves = pd.isna(eleves) or abs(filles + garcons - eleves) < 1
            controle_enseignants = pd.isna(enseignants) or abs(femmes + hommes - enseignants) < 1
            if not (controle_eleves and controle_enseignants):
                journal.noter(table, "signalement", "somme filles + garçons ou femmes + hommes différente du total "
                              "(lecture OCR à vérifier)", source=fichier, page=row["page"], ligne=row["ligne"],
                              avant=texte)
            lignes.append({
                "mois": mois,
                "type": type_tableau,
                "province_ancienne_pcode": code,
                "nom_source": cel[position],
                "etablissements": etab,
                "eleves_filles": filles,
                "eleves_garcons": garcons,
                "eleves_total": eleves,
                "enseignants_femmes": femmes,
                "enseignants_hommes": hommes,
                "enseignants_total": enseignants,
                "ligne_coherente": bool(controle_eleves and controle_enseignants),
                "methode_lecture": methode or "texte natif",
                "source_fichier": fichier,
                "page": row["page"],
            })

    return pd.DataFrame(lignes), pd.DataFrame(totaux)


_REGIONS = (r"Boucle du Mouhoun|Cascades|Centre[- ]Est|Centre[- ]Nord|Centre[- ]Ouest|Centre[- ]Sud|Centre|Est|"
             r"Hauts[- ]Bassins|Nord|Plateau[- ]Central|Sahel|Sud[- ]Ouest")
_PHRASE = re.compile(
    rf"({_REGIONS})\s*[:;]?\s*(\d[\d\s]*?)\s*(?:établissements?|structures?)\s+(?:scolaires\s+)?(?:éducatives\s+)?"
    r"fermé\w*\s*,?\s*affectant\s+(\d[\d\s]*?)\s*élèves\s+dont\s+(\d[\d\s]*?)\s*filles"
    r"(?:\s*,?\s*ainsi\s+que\s+(\d[\d\s]*?)\s*enseignants)?",
    re.IGNORECASE,
)


def _entier(texte: str | None) -> float:
    return float(re.sub(r"\s", "", texte)) if texte else float("nan")


def lire_esu_regions(identifier: Identification, journal: Journal) -> pd.DataFrame:
    """Établissements fermés par région, tous ordres d'enseignement, d'après le texte des rapports.

    Les rapports résument la situation de chaque région en une phrase (« Est : 1 090
    établissements scolaires fermés, affectant 189 095 élèves dont 90 961 filles,
    ainsi que 5 914 enseignants »). Ce texte résiste mieux à la reconnaissance de
    caractères que les tableaux ; il couvre les rapports de novembre 2021 à mai 2023.
    Les rapports postérieurs ne recensent plus les fermetures, seulement les réouvertures.
    """
    brut = lire_extrait("esu_rapports_mensuels")
    brut = brut.assign(_p=pd.to_numeric(brut["page"]), _l=pd.to_numeric(brut["ligne"])).sort_values(
        ["source_fichier", "_p", "_l"])
    colonnes = colonnes_cellules(brut)
    lignes = []
    for fichier, bloc in brut.groupby("source_fichier", sort=False):
        texte = re.sub(r"\s+", " ", " ".join(bloc[colonnes].agg(" ".join, axis=1)))
        vues = set()
        for m in _PHRASE.finditer(texte):
            region = identifier(m.group(1))
            if region is None or region[1] != "region_ancienne" or region[0] in vues:
                continue
            vues.add(region[0])
            lignes.append({
                "mois": bloc["source_periode"].iloc[0],
                "region_ancienne_pcode": region[0],
                "etablissements_fermes": _entier(m.group(2)),
                "eleves_affectes": _entier(m.group(3)),
                "eleves_affectes_filles": _entier(m.group(4)),
                "enseignants_affectes": _entier(m.group(5)),
                "methode_lecture": (bloc["methode"].iloc[0] if "methode" in bloc else "") or "texte natif",
                "source_fichier": fichier,
            })
        if not vues:
            journal.noter("fait_esu_region", "rapport sans fermetures", "aucune phrase de synthèse des fermetures "
                          "par région dans ce rapport", source=fichier, avant=bloc["source_periode"].iloc[0])
    return pd.DataFrame(lignes)


def controle_totaux(esu: pd.DataFrame, totaux: pd.DataFrame) -> pd.DataFrame:
    """Somme des provinces comparée au total primaire publié dans chaque rapport."""
    if esu.empty:
        return pd.DataFrame()
    somme = esu.groupby(["source_fichier", "mois", "type"])[["etablissements", "eleves_total"]].sum(min_count=1)
    somme = somme.rename(columns=lambda c: f"{c}_somme").reset_index()
    res = somme.merge(totaux, on=["source_fichier", "mois", "type"], how="left")
    res["ecart_etablissements"] = res["etablissements_somme"] - res["etablissements_publie"]
    res["ecart_eleves"] = res["eleves_total_somme"] - res["eleves_total_publie"]
    return res.sort_values(["type", "mois"])
