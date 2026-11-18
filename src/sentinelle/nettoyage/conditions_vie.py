"""Pauvreté et conditions de vie par commune (INSD, RGPH 2019, volume 3, annexes 4 à 9).

La publication « Mesure et cartographie de la pauvreté » (INSD, novembre 2022) donne,
pour le pays, les 13 régions, les 45 provinces, les 369 communes et arrondissements et
les secteurs, 33 indicateurs répartis en six annexes :

- annexe 4 : code RGPH, nom, population, ménages, incidence et profondeur de la
  pauvreté, nombre de pauvres ;
- annexes 5 à 9 : cinq indicateurs chacune (emploi et chômage, scolarisation et
  enfants hors de l'école, alphabétisation, mariage précoce, actes de naissance,
  accès à l'eau, à l'électricité, au téléphone...), sans code, dans le même ordre
  que l'annexe 4.

Les noms des annexes 5 à 9 (« Secteur 2 » revient des centaines de fois) sont alignés
sur ceux de l'annexe 4 par appariement de séquences : une ligne n'est rattachée que
si son nom concorde avec celui de l'entité au même rang de la séquence alignée.

Les arrondissements de Ouagadougou et de Bobo-Dioulasso sont regroupés dans leur
commune (effectifs sommés, taux pondérés par la population). Les valeurs hors de leur
domaine (taux supérieur à 100, rapport filles / garçons supérieur à 3) sont signalées,
jamais corrigées.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher, get_close_matches

import numpy as np
import pandas as pd

from .outils import Journal, cellules, colonnes_cellules, en_nombre, est_nombre, lire_extrait, normaliser_nom

TABLE = "fait_conditions_vie"
ANNEXE_4 = ["population", "menages", "incidence_pauvrete", "profondeur_pauvrete", "nombre_pauvres"]
ANNEXES = {
    "A5": ("ch.mage", ["emploi_7_14", "emploi_15_24", "emploi_25_64", "chomage_15_24", "chomage_25_64"]),
    "A6": ("autonomes", ["travailleurs_autonomes_15_24", "travailleurs_autonomes_25_64", "frequentation_postprimaire",
                         "frequentation_lycee", "ratio_filles_garcons_primaire"]),
    "A7": ("hors", ["ratio_filles_garcons_post_primaire", "ratio_filles_garcons_secondaire", "hors_ecole_6_11",
                    "hors_ecole_12_15", "hors_ecole_16_18"]),
    "A8": ("naissance|alphab", ["ni_ecole_ni_travail_15_24", "alphabetisation_15_64", "dependance_demographique",
                                "filles_17_ans_mariees", "acte_naissance"]),
    "A9": ("lectricit|sanitaires|cuisson|t.l.phone", ["sanitaires_ameliores", "eau_amelioree", "electricite",
                                                      "energie_cuisson_amelioree", "telephone"]),
}
INDICATEURS = ANNEXE_4 + [v for _, (_m, colonnes) in ANNEXES.items() for v in colonnes]
COMPTAGES = ["population", "menages", "nombre_pauvres"]
RAPPORTS = [c for c in INDICATEURS if c.startswith("ratio_")]
_CODE = re.compile(r"^(\d{1,2}) (\d\d) (\d\d) (\d\d)$")


def _niveau(code: str) -> str:
    if code == "BF":
        return "pays"
    region, province, commune, secteur = _CODE.match(code).groups()
    if province == "00":
        return "region_ancienne"
    if commune == "00":
        return "province_ancienne"
    return "commune_rgph" if secteur == "00" else "secteur"


def _lignes(brut: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lignes de l'annexe 4 (avec code) et lignes de données des annexes 5 à 9 (nom et cinq valeurs)."""
    colonnes = colonnes_cellules(brut)
    brut = brut.assign(_page=pd.to_numeric(brut["page"]), _ligne=pd.to_numeric(brut["ligne"])).sort_values(
        ["_page", "_ligne"])
    annexe4, autres = [], []
    for _, row in brut.iterrows():
        cel = cellules(row, colonnes)
        if len(cel) == 7 and _CODE.match(cel[0]) and all(est_nombre(c) for c in cel[2:]):
            annexe4.append({"code_rgph": cel[0], "libelle": cel[1], **dict(zip(ANNEXE_4, map(en_nombre, cel[2:]))),
                            "page": row["_page"]})
        elif len(cel) == 6 and cel[0] == "BURKINA FASO" and all(est_nombre(c) for c in cel[1:]) and not annexe4:
            annexe4.append({"code_rgph": "BF", "libelle": cel[0], **dict(zip(ANNEXE_4, map(en_nombre, cel[1:]))),
                            "page": row["_page"]})
        elif len(cel) == 6 and not est_nombre(cel[0]) and all(est_nombre(c) for c in cel[1:]):
            autres.append({"libelle": cel[0], "valeurs": [en_nombre(c) for c in cel[1:]], "page": row["_page"]})
    return pd.DataFrame(annexe4), pd.DataFrame(autres)


def _annexes(brut: pd.DataFrame, autres: pd.DataFrame) -> pd.Series:
    """Annexe de chaque page de données : début d'annexe repéré par les mots de l'en-tête, en séquence."""
    colonnes = colonnes_cellules(brut)
    texte = brut[colonnes].apply(lambda r: " ".join(v for v in r if v), axis=1)
    tetes = texte.groupby(pd.to_numeric(brut["page"])).apply(lambda s: " ".join(s.head(12)))
    pages = sorted(autres["page"].unique())
    debuts, depuis = {}, pages[0]
    for annexe, (motif, _colonnes) in ANNEXES.items():
        debut = next(p for p in pages if p >= depuis and re.search(motif, tetes.get(p, ""), re.I))
        debuts[annexe], depuis = debut, debut + 1
    bornes = sorted(debuts.items(), key=lambda x: x[1])
    return autres["page"].map(lambda p: next((a for a, d in reversed(bornes) if p >= d), None))


def _aligner(reference: list[str], lus: list[str]) -> dict[int, int]:
    """Indices des lignes lues rattachées aux lignes de référence (noms normalisés identiques, dans l'ordre)."""
    correspondance = {}
    for bloc in SequenceMatcher(None, reference, lus, autojunk=False).get_matching_blocks():
        for k in range(bloc.size):
            correspondance[bloc.a + k] = bloc.b + k
    return correspondance


def lire_rgph(journal: Journal) -> pd.DataFrame:
    """Les 33 indicateurs pour chaque entité de l'annexe 4, dans le découpage du RGPH 2019."""
    brut = lire_extrait("rgph_cartographie_pauvrete")
    table, autres = _lignes(brut)
    autres["annexe"] = _annexes(brut, autres)
    reference = [normaliser_nom(n) for n in table["libelle"]]
    for annexe, (_motif, colonnes) in ANNEXES.items():
        partie = autres[autres["annexe"] == annexe].reset_index(drop=True)
        lus = [normaliser_nom(n) for n in partie["libelle"]]
        lien = _aligner(reference, lus)
        valeurs = np.full((len(table), len(colonnes)), np.nan)
        for i, j in lien.items():
            valeurs[i] = partie.at[j, "valeurs"]
        table[colonnes] = valeurs
        manquants = len(table) - len(lien)
        if manquants:
            journal.noter(TABLE, "signalement", f"annexe {annexe[1:]} : entités sans ligne rattachée, valeurs laissées vides",
                          source="NADA275_RGPH2019_Cartographie_pauvrete.pdf",
                          avant=", ".join(table.loc[[i for i in range(len(table)) if i not in lien], "libelle"].head(12)),
                          apres=str(manquants))
    table["niveau_rgph"] = table["code_rgph"].map(_niveau)
    return table


def _rattacher(table: pd.DataFrame, communes: pd.DataFrame, alias: pd.DataFrame, journal: Journal) -> pd.DataFrame:
    """P-codes : régions et provinces par leur nom, communes par leur nom dans leur province."""
    codes = dict(zip(alias["nom_normalise"], alias["pcode"]))
    table = table.copy()
    table["region_rgph"] = table["code_rgph"].str.extract(r"^(\d{1,2}) ")[0]
    table["province_rgph"] = table["code_rgph"].str.extract(r"^(\d{1,2} \d\d) ")[0]
    noms_regions = table[table["niveau_rgph"] == "region_ancienne"].set_index("region_rgph")["libelle"]
    noms_provinces = table[table["niveau_rgph"] == "province_ancienne"].set_index("province_rgph")["libelle"]
    table["region_ancienne_pcode"] = table["region_rgph"].map(noms_regions).map(lambda n: codes.get(normaliser_nom(n))
                                                                                if isinstance(n, str) else None)
    table["province_ancienne_pcode"] = table["province_rgph"].map(noms_provinces).map(
        lambda n: codes.get(normaliser_nom(n)) if isinstance(n, str) else None)

    par_province = {p: dict(zip(g["commune_nom"].map(normaliser_nom), g["commune_pcode"]))
                    for p, g in communes.groupby("province_ancienne_pcode")}
    # Arrondissements regroupés dans leur commune ; orthographes trop éloignées pour le rapprochement automatique.
    speciaux = {"OUAGAARR": "OUAGADOUGOU", "BOBOARR": "BOBODIOULASSO", "BOBORURAL": "BOBODIOULASSO",
                "GOURCY": "GOURSI"}
    pcodes = []
    for r in table.itertuples():
        if r.niveau_rgph not in ("commune_rgph", "secteur"):
            pcodes.append(None)
            continue
        candidats = par_province.get(r.province_ancienne_pcode, {})
        libelle = r.libelle if r.niveau_rgph == "commune_rgph" else None
        if libelle is None:
            pcodes.append(None)
            continue
        cle = normaliser_nom(libelle)
        cle = next((v for k, v in speciaux.items() if cle.startswith(k)), cle)
        trouve = candidats.get(cle) or next(iter(get_close_matches(cle, list(candidats), n=1, cutoff=0.7)), None)
        if trouve and trouve not in candidats.values():
            trouve = candidats[trouve]
        if trouve is None:
            journal.noter(TABLE, "signalement", "commune du RGPH sans correspondance COD-AB", avant=libelle,
                          apres=str(r.province_ancienne_pcode))
        elif normaliser_nom(libelle) not in candidats and not any(normaliser_nom(libelle).startswith(k) for k in speciaux):
            nom = next(k for k, v in candidats.items() if v == trouve)
            journal.noter(TABLE, "rapprochement", "commune rapprochée par orthographe voisine", avant=libelle, apres=nom)
        pcodes.append(trouve)
    table["commune_pcode"] = pcodes
    # Les secteurs héritent de la commune qui les précède.
    est_commune = table["niveau_rgph"] == "commune_rgph"
    table["commune_pcode"] = table["commune_pcode"].where(est_commune).ffill().where(
        table["niveau_rgph"].isin(["commune_rgph", "secteur"]))
    return table


def _regrouper_communes(rgph: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par commune COD-AB : arrondissements sommés, taux pondérés par la population."""
    communes = rgph[rgph["niveau_rgph"] == "commune_rgph"].dropna(subset=["commune_pcode"])
    taux = [c for c in INDICATEURS if c not in COMPTAGES]
    agreges = communes.groupby("commune_pcode").apply(
        lambda g: pd.Series({**{c: g[c].sum(min_count=1) for c in COMPTAGES},
                             **{c: np.average(g[c].dropna(), weights=g.loc[g[c].notna(), "population"])
                                if g[c].notna().any() else np.nan for c in taux},
                             "libelle": " + ".join(g["libelle"]) if len(g) > 1 else g["libelle"].iloc[0],
                             "code_rgph": ", ".join(g["code_rgph"]), "nb_unites_rgph": len(g),
                             "page": g["page"].min()}), include_groups=False)
    agreges["incidence_pauvrete"] = np.where(agreges["nb_unites_rgph"] > 1,
                                            100 * agreges["nombre_pauvres"] / agreges["population"],
                                            agreges["incidence_pauvrete"])
    return agreges.reset_index()


def construire(communes: pd.DataFrame, alias: pd.DataFrame, journal: Journal) -> pd.DataFrame:
    """Table finale : pays, régions, provinces (anciennes) et communes COD-AB, 33 indicateurs."""
    rgph = _rattacher(lire_rgph(journal), communes, alias, journal)
    lignes = []
    for niveau, cle in [("pays", None), ("region_ancienne", "region_ancienne_pcode"),
                        ("province_ancienne", "province_ancienne_pcode")]:
        partie = rgph[rgph["niveau_rgph"] == niveau].copy()
        partie["entite_pcode"] = "BF" if cle is None else partie[cle]
        partie["nb_unites_rgph"] = 1
        lignes.append(partie)
    commune = _regrouper_communes(rgph).rename(columns={"commune_pcode": "entite_pcode"})
    commune["niveau_rgph"] = "commune"
    lignes.append(commune)
    table = pd.concat(lignes, ignore_index=True).rename(columns={"niveau_rgph": "niveau_geo"})
    # Signalements : valeurs hors de leur domaine, conservées telles quelles.
    pourcentages = [c for c in INDICATEURS if c not in COMPTAGES + RAPPORTS]
    anomalies = []
    for r in table.itertuples():
        hors_domaine = [c for c in pourcentages if getattr(r, c) > 100] + [c for c in RAPPORTS if getattr(r, c) > 3]
        anomalies.append(", ".join(hors_domaine))
        if hors_domaine:
            journal.noter(TABLE, "signalement", "valeur hors de son domaine dans la publication, conservée",
                          source="NADA275_RGPH2019_Cartographie_pauvrete.pdf", page=str(r.page),
                          avant=f"{r.libelle} : " + ", ".join(f"{c} = {getattr(r, c):g}" for c in hors_domaine))
    table["valeurs_hors_domaine"] = anomalies
    table["annee_reference"] = 2019
    table["source_fichier"] = "NADA275_RGPH2019_Cartographie_pauvrete.pdf"
    colonnes = (["niveau_geo", "entite_pcode", "libelle", "code_rgph", "nb_unites_rgph", "annee_reference"] + INDICATEURS
                + ["valeurs_hors_domaine", "source_fichier", "page"])
    return table[colonnes].sort_values(["niveau_geo", "entite_pcode"]).reset_index(drop=True)


def controler(table: pd.DataFrame, communes_ref: pd.DataFrame, fichier_controle) -> dict[str, tuple[bool, str]]:
    resultats = {}
    n = table.groupby("niveau_geo")["entite_pcode"].nunique()
    resultats["conditions_vie_couverture"] = (
        n.get("region_ancienne") == 13 and n.get("province_ancienne") == 45 and n.get("commune", 0) >= 345,
        f"{n.get('region_ancienne', 0)} régions, {n.get('province_ancienne', 0)} provinces, "
        f"{n.get('commune', 0)} communes sur {communes_ref['commune_pcode'].nunique()}")
    com = table[table["niveau_geo"] == "commune"].merge(communes_ref[["commune_pcode", "province_ancienne_pcode"]],
                                                        left_on="entite_pcode", right_on="commune_pcode")
    somme = com.groupby("province_ancienne_pcode")["population"].sum()
    prov = table[table["niveau_geo"] == "province_ancienne"].set_index("entite_pcode")["population"]
    ecart = (somme - prov.reindex(somme.index)).abs()
    resultats["conditions_vie_population_communes_egal_province"] = (
        bool((ecart <= 1).mean() >= 0.95), f"{int((ecart <= 1).sum())} provinces sur {len(ecart)} identiques")
    remplissage = table[INDICATEURS].notna().mean()
    resultats["conditions_vie_indicateurs_renseignes"] = (
        bool(remplissage.min() >= 0.97),
        f"part renseignée de 33 indicateurs : minimum {remplissage.min():.1%} ({remplissage.idxmin()})")
    if fichier_controle is not None and fichier_controle.exists():
        ext = pd.read_excel(fichier_controle, sheet_name="Toutes_zones", dtype={"code_rgph": str})
        ext = ext[ext["niveau"].isin(["Pays", "Région", "Province", "Commune / arrondissement"])]
        ext["code_rgph"] = ext["code_rgph"].replace({"NATIONAL": "BF"})
        nous = table[(table["niveau_geo"] != "commune") | (table["nb_unites_rgph"] == 1)].set_index("code_rgph")
        # Les 30 indicateurs de l'annexe : nom Sentinelle -> colonne du classeur de l'équipe (même nom, suffixe _pct).
        speciaux = {"population": "population_2019", "menages": "nombre_menages_2019", "nombre_pauvres": "nombre_pauvres",
                    "ratio_filles_garcons_post_primaire": "ratio_filles_garcons_moyen"}
        indicateurs = [c for c in table.columns if c in speciaux or f"{c}_pct" in ext.columns or c in ext.columns]
        correspondance = {c: speciaux.get(c, f"{c}_pct" if f"{c}_pct" in ext.columns else c) for c in indicateurs
                          if c not in ("code_rgph", "niveau_geo", "libelle", "population_2019")}
        correspondance = {a: b for a, b in correspondance.items() if b in ext.columns}
        ext = ext.set_index("code_rgph")
        commun = nous.index.intersection(ext.index)
        egal = total = 0
        for a, b in correspondance.items():
            x, y = nous.loc[commun, a].astype(float), pd.to_numeric(ext.loc[commun, b], errors="coerce")
            total += int((x.notna() & y.notna()).sum())
            egal += int(((x - y).abs() <= 0.05).sum())
        resultats["conditions_vie_identique_extraction_equipe"] = (
            total > 0 and egal / total >= 0.98,
            f"pays, régions, provinces et communes : {egal} valeurs identiques sur {total} comparées ({len(correspondance)} indicateurs) "
            "avec l'extraction indépendante d'un membre de l'équipe")
    return resultats
