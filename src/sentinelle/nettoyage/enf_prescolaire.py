"""Éducation non formelle et préscolaire par province.

Éducation non formelle (annuaires de la DGESS, campagnes 2018, 2019, 2020 et 2024)
    Tableau 1.1 : centres (adultes, adolescents) et apprenants, par province et milieu.
    Tableau 1.3 : apprenants par type d'éducation (adultes 1er et 2nd cycle,
    adolescents), total et dont femmes, par province et milieu.
    Chaque province occupe une ligne de nom puis trois lignes (rural, urbain, total).
    La campagne est lue dans l'en-tête des pages, jamais dans le nom du fichier : deux
    fichiers du Data Pack (CNS517 « 2019 » et CNS519 « 2021 ») sont identiques et
    portent la campagne 2020, et CNS518 (« 2020 ») porte la campagne 2019. Un fichier
    dont la campagne est déjà lue est écarté comme doublon.

Préscolaire (annuaires 2023-2024 et 2024-2025)
    Tableau 02 : population préscolarisable, population préscolarisée et taux de
    préscolarisation, par province et sexe.
    Tableau 9 (11 en 2023-2024) : enfants inscrits par province, sexe et section.
    Chaque entité occupe trois lignes (filles, garçons, ensemble). Le nom de la région,
    centré verticalement dans le PDF, tombe souvent au milieu du bloc d'une province
    (« BOUCLE DU » puis « MOUHOUN » dans le bloc de la province du Mouhoun), et le
    total régional n'est pas toujours intitulé « TOTAL REGION ». Chaque bloc est donc lu
    en entier : les noms de région en sont d'abord retirés, puis le reste est reconnu
    comme province ; un bloc sans province est le total de la région.
"""

from __future__ import annotations

import re

import pandas as pd

from .dgess import Identification, _trier
from .outils import Journal, cellules, colonnes_cellules, en_nombre, est_nombre, lire_extrait, normaliser_nom

MILIEUX = {"RURAL": "rural", "URBAIN": "urbain", "TOTAL": "total"}
COLONNES_ENF = {
    "1.1": ["centres_adultes", "centres_adolescents", "centres_total", "apprenants_total", "apprenants_femmes"],
    "1.3": ["adultes_1er_cycle", "adultes_1er_cycle_femmes", "adultes_2nd_cycle", "adultes_2nd_cycle_femmes",
            "adultes_total", "adultes_total_femmes", "adolescents", "adolescents_filles",
            "apprenants_total_t13", "apprenants_femmes_t13"],
}
SEXES = {"FILLES": "F", "GARCONS": "G", "ENSEMBLE": "T"}
COLONNES_PRESCOLAIRE = {
    "02": ["population_prescolarisable", "enfants_prescolarises", "taux_prescolarisation"],
    "9": ["petite_section", "moyenne_section", "grande_section", "enfants_inscrits"],
}
_ENTETE_PRESCOLAIRE = re.compile(
    r"(?i)popul|taux|r[ée]gions?|provinces?|^sexe|section|petite|moyenne|grande|^total$|pr[ée]scolaris|en %|"
    r"\d|suite|tableau|r[ée]partition|auditeurs")


def _campagne(bloc: pd.DataFrame, colonnes: list[str]) -> int | None:
    textes = bloc[colonnes].apply(lambda r: " ".join(v for v in r if v), axis=1)
    annees = textes.str.extract(r"CAMPAGNE\s*:?\s*(20\d\d)")[0].dropna()
    return int(annees.mode().iloc[0]) if len(annees) else None


def _tableau_enf(textes: pd.Series) -> pd.Series:
    """Tableau de chaque page (1.1, 1.3 ou autre), d'après le titre en majuscules de la page."""
    titre = textes.str.extract(r"^TABLEAU\s*(1\.[13])\s*:")[0]
    return titre


def lire_enf(identifier: Identification, journal: Journal) -> pd.DataFrame:
    table = "fait_enf_province"
    brut = _trier(lire_extrait("dgess_non_formelle_annuaires"))
    colonnes = colonnes_cellules(brut)
    brut["_texte"] = brut[colonnes].apply(lambda r: " ".join(v.strip() for v in r if v.strip()), axis=1)
    lignes, campagnes_lues = [], {}
    for fichier, bloc in brut.groupby("source_fichier", sort=False):
        campagne = _campagne(bloc, colonnes)
        if campagne in campagnes_lues:
            journal.noter(table, "fichier écarté", "doublon : même campagne déjà lue dans un autre fichier",
                          source=fichier, avant=str(campagne), apres=campagnes_lues[campagne])
            continue
        campagnes_lues[campagne] = fichier
        if str(campagne) not in fichier:
            journal.noter(table, "signalement", "la campagne de l'en-tête diffère de l'année du nom du fichier",
                          source=fichier, apres=str(campagne))
        # Tableau de chaque page : le titre figure en tête de page.
        titres = bloc.groupby("page")["_texte"].apply(lambda s: _tableau_enf(s).dropna().iloc[0]
                                                      if _tableau_enf(s).notna().any() else None)
        pages = titres[titres.notna()]
        entite = region = None
        for _, row in bloc[bloc["page"].isin(pages.index)].iterrows():
            tableau = pages[row["page"]]
            cel = cellules(row, colonnes)
            textes = [c for c in cel if not est_nombre(c)]
            nombres = [en_nombre(c) for c in cel if est_nombre(c)]
            if not cel:
                continue
            milieu = MILIEUX.get(normaliser_nom(cel[0]))
            attendu = len(COLONNES_ENF[tableau])
            if milieu and len(nombres) == attendu and len(textes) == 1:
                if entite is None:
                    continue
                lignes.append({"campagne": campagne, "tableau": tableau, "entite_pcode": entite[0],
                               "niveau_geo": entite[1], "milieu": milieu,
                               **dict(zip(COLONNES_ENF[tableau], nombres)),
                               "source_fichier": fichier, "page": row["page"]})
                continue
            if nombres and not milieu:
                if len(nombres) == attendu:
                    journal.noter(table, "ligne écartée", "valeurs sans libellé de milieu", source=fichier,
                                  page=str(row["page"]), ligne=str(row["ligne"]), avant=" ".join(cel)[:120])
                continue
            if textes and not nombres:
                nom = normaliser_nom(" ".join(textes))
                if nom.startswith("TOTALREGION"):
                    entite = region
                elif nom.startswith("TOTALNATIONAL"):
                    entite = ("BF", "pays")
                elif (trouve := identifier(" ".join(textes))) is not None and trouve[1] != "pays":
                    entite = trouve
                    if trouve[1] == "region_ancienne":
                        region = trouve

    long = pd.DataFrame(lignes)
    cles = ["campagne", "entite_pcode", "niveau_geo", "milieu"]
    doublons = long.duplicated(cles + ["tableau"], keep="first")
    for r in long[doublons].itertuples():
        journal.noter(table, "ligne écartée", "entité répétée dans le même tableau", source=r.source_fichier,
                      page=str(r.page), avant=f"{r.tableau} {r.entite_pcode} {r.milieu}")
    long = long[~doublons]
    t11 = long.loc[long["tableau"] == "1.1", cles + COLONNES_ENF["1.1"] + ["source_fichier", "page"]]
    t13 = long.loc[long["tableau"] == "1.3", cles + COLONNES_ENF["1.3"]]
    large = t11.merge(t13, on=cles, how="outer")
    large = large[cles + COLONNES_ENF["1.1"] + COLONNES_ENF["1.3"] + ["source_fichier", "page"]]
    large["annee_scolaire"] = (large["campagne"] - 1).astype(str) + "-" + large["campagne"].astype(str)
    return large.sort_values(cles).reset_index(drop=True)


def _tableau_prescolaire(textes: pd.Series) -> str | None:
    """Tableau d'une page du préscolaire ; une page de sommaire (plusieurs titres) est ignorée."""
    titres = textes[textes.str.contains(r"(?i)tableau\s*\d+\s*:")]
    if len(titres) != 1:
        return None
    texte = " ".join(textes.head(8))
    if re.search(r"(?i)tableau\s*0?2\s*:", texte) and re.search(r"(?i)taux", texte) \
            and re.search(r"(?i)province", texte):
        return "02"
    # Le numéro change d'une édition à l'autre (11 en 2023-2024, 9 en 2024-2025) : l'intitulé fait foi.
    if re.search(r"(?i)auditeurs par r[ée]gion, par province et par sexe", texte) and \
            not re.search(r"(?i)handicap", texte):
        return "9"
    return None


def lire_prescolaire(identifier: Identification, alias: pd.DataFrame, journal: Journal) -> pd.DataFrame:
    table = "fait_prescolaire_province"
    brut = _trier(lire_extrait("dgess_prescolaire"))
    brut = brut[brut["source_fichier"].str.contains(r"Annuaire", case=False)]
    colonnes = colonnes_cellules(brut)
    brut["_texte"] = brut[colonnes].apply(lambda r: " ".join(v.strip() for v in r if v.strip()), axis=1)
    regions = alias[alias["niveau"] == "region_ancienne"]
    noms_regions = sorted(regions["nom_normalise"], key=len, reverse=True)
    code_region = dict(zip(regions["nom_normalise"], regions["pcode"]))

    lignes = []
    for fichier, bloc in brut.groupby("source_fichier", sort=False):
        m = re.search(r"(20\d\d)_(20\d\d)", fichier)
        annee = f"{m.group(1)}-{m.group(2)}"
        for page, contenu in bloc.groupby("page", sort=False):
            tableau = _tableau_prescolaire(contenu["_texte"])
            if tableau is None:
                continue
            attendu = len(COLONNES_PRESCOLAIRE[tableau])
            noms, valeurs, region_courante = [], {}, None
            for _, row in contenu.iterrows():
                cel = cellules(row, colonnes)
                sexe = next((SEXES[normaliser_nom(c)] for c in cel if normaliser_nom(c) in SEXES), None)
                textes = [c for c in cel if not est_nombre(c) and normaliser_nom(c) not in SEXES]
                noms += [t for t in textes if not _ENTETE_PRESCOLAIRE.search(t) or normaliser_nom(t) == "TOTALREGION"]
                if sexe is None:
                    continue
                nombres = [en_nombre(c) for c in cel if est_nombre(c)]
                if len(nombres) != attendu:
                    journal.noter(table, "ligne écartée", f"{len(nombres)} valeurs au lieu de {attendu}",
                                  source=fichier, page=str(page), ligne=str(row["ligne"]), avant=" ".join(cel)[:120])
                    continue
                valeurs[sexe] = nombres
                if sexe != "T":
                    continue
                # Fin de bloc : identification de l'entité.
                reste = normaliser_nom(" ".join(noms))
                total_region = "TOTALREGION" in reste
                reste = reste.replace("TOTALREGION", "")
                region_lue = None
                for nom in noms_regions:
                    if nom in reste:
                        reste = reste.replace(nom, "", 1)
                        region_lue = code_region[nom]
                        break
                region_courante = region_lue or region_courante
                if reste in ("TOTALNATIONAL", "BURKINAFASO", "NATIONAL"):
                    entite = ("BF", "pays")
                elif reste and (trouve := identifier(reste)) is not None and trouve[1] == "province_ancienne":
                    entite = trouve
                elif not reste and (total_region or region_lue) and region_courante:
                    entite = (region_courante, "region_ancienne")
                else:
                    journal.noter(table, "ligne écartée", "entité non reconnue", source=fichier, page=str(page),
                                  avant=" ".join(noms)[:120])
                    entite = None
                if entite is not None:
                    for s, v in valeurs.items():
                        lignes.append({"annee_scolaire": annee, "tableau": tableau, "entite_pcode": entite[0],
                                       "niveau_geo": entite[1], "sexe": s,
                                       **dict(zip(COLONNES_PRESCOLAIRE[tableau], v)),
                                       "source_fichier": fichier, "page": page})
                noms, valeurs = [], {}

    long = pd.DataFrame(lignes)
    cles = ["annee_scolaire", "entite_pcode", "niveau_geo", "sexe"]
    long = long.drop_duplicates(cles + ["tableau"], keep="first")
    t02 = long.loc[long["tableau"] == "02", cles + COLONNES_PRESCOLAIRE["02"] + ["source_fichier", "page"]]
    t9 = long.loc[long["tableau"] == "9", cles + COLONNES_PRESCOLAIRE["9"]]
    large = t02.merge(t9, on=cles, how="outer")
    large = large[cles + COLONNES_PRESCOLAIRE["02"] + COLONNES_PRESCOLAIRE["9"] + ["source_fichier", "page"]]
    return large.sort_values(cles).reset_index(drop=True)


# Contrôles ------------------------------------------------------------------------------------------

def controler(enf: pd.DataFrame, prescolaire: pd.DataFrame, base_principale: pd.DataFrame,
              region_de: dict[str, str]) -> dict[str, tuple[bool, str]]:
    resultats = {}
    # ENF : provinces par campagne, cohérences internes.
    prov = enf[(enf["niveau_geo"] == "province_ancienne") & (enf["milieu"] == "total")]
    n = prov.groupby("campagne")["entite_pcode"].nunique()
    resultats["enf_provinces_par_campagne"] = (
        bool((n >= 44).all()), "; ".join(f"campagne {c} : {v}" for c, v in n.items()))
    ecart_tableaux = (enf["apprenants_total"] - enf["apprenants_total_t13"]).abs()
    ecart_types = (enf["adultes_total"] + enf["adolescents"] - enf["apprenants_total_t13"]).abs()
    ecart_centres = (enf["centres_adultes"] + enf["centres_adolescents"] - enf["centres_total"]).abs()
    resultats["enf_coherence_tableaux"] = (
        bool((ecart_tableaux.dropna() == 0).mean() > 0.97 and (ecart_types.dropna() == 0).mean() > 0.97
             and (ecart_centres.dropna() == 0).mean() > 0.97),
        f"apprenants 1.1 = 1.3 : {int((ecart_tableaux == 0).sum())} sur {ecart_tableaux.notna().sum()} ; "
        f"adultes + adolescents = total : {int((ecart_types == 0).sum())} sur {ecart_types.notna().sum()} ; "
        f"centres adultes + adolescents = total : {int((ecart_centres == 0).sum())} sur {ecart_centres.notna().sum()}")
    large = enf.pivot_table(index=["campagne", "entite_pcode"], columns="milieu", values="apprenants_total")
    if {"rural", "urbain", "total"} <= set(large.columns):
        e = (large["rural"].fillna(0) + large["urbain"].fillna(0) - large["total"]).abs().dropna()
        resultats["enf_rural_plus_urbain_egal_total"] = (bool((e == 0).mean() > 0.97),
                                                         f"{int((e == 0).sum())} sur {len(e)} identiques")
    somme = prov.assign(region=prov["entite_pcode"].map(region_de)).groupby(["campagne", "region"])[
        "apprenants_total"].sum()
    publie = enf[(enf["niveau_geo"] == "region_ancienne") & (enf["milieu"] == "total")].set_index(
        ["campagne", "entite_pcode"])["apprenants_total"]
    publie.index = publie.index.set_names(["campagne", "region"])
    commun = somme.index.intersection(publie.index)
    e = (somme.loc[commun] - publie.loc[commun]).abs()
    resultats["enf_somme_provinces_egal_region"] = (bool((e == 0).mean() > 0.9),
                                                    f"{int((e == 0).sum())} régions × campagnes identiques sur {len(e)}")

    # Préscolaire.
    p = prescolaire[(prescolaire["niveau_geo"] == "province_ancienne") & (prescolaire["sexe"] == "T")]
    n = p.groupby("annee_scolaire")["entite_pcode"].nunique()
    resultats["prescolaire_provinces_par_annee"] = (bool((n == 45).all()),
                                                    "; ".join(f"{a} : {v}" for a, v in n.items()))
    e = (prescolaire["enfants_prescolarises"] - prescolaire["enfants_inscrits"]).abs().dropna()
    s = (prescolaire[["petite_section", "moyenne_section", "grande_section"]].sum(axis=1)
         - prescolaire["enfants_inscrits"]).abs()[prescolaire["enfants_inscrits"].notna()]
    resultats["prescolaire_tableaux_02_et_9_coherents"] = (
        bool((e == 0).mean() > 0.95 and (s == 0).mean() > 0.95),
        f"préscolarisés (tableau 02) = inscrits (tableau 9) : {int((e == 0).sum())} sur {len(e)} ; "
        f"somme des sections = total : {int((s == 0).sum())} sur {len(s)}")
    reg = prescolaire[(prescolaire["niveau_geo"] == "region_ancienne") & (prescolaire["sexe"] == "T")]
    bp = base_principale[(base_principale["tableau"] == "PRESCOLAIRE T1") & (base_principale["sexe"] == "T")]
    bp = bp.set_index(["annee_scolaire", "entite_pcode"])["valeur"]
    lu = reg.set_index(["annee_scolaire", "entite_pcode"])["enfants_inscrits"].dropna()
    commun = lu.index.intersection(bp.index)
    e = (lu.loc[commun] - bp.loc[commun]).abs()
    resultats["prescolaire_regions_egal_base_principale"] = (
        bool(len(e) > 0 and (e == 0).mean() > 0.9),
        f"{int((e == 0).sum())} régions × années identiques à la base principale sur {len(e)}")
    return resultats
