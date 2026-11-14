"""Étape 02 : nettoyage et construction de la base Sentinelle Scolaire.

La base est un GeoPackage unique : couches cartographiques des deux découpages,
tables de référence, tables de faits nettoyées et tables de traçabilité. Chaque
table est aussi exportée en CSV pour les dépôts.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

from .. import config
from ..indicateurs import effectifs_retenus
from . import base_principale as principale
from . import conditions_vie, enf_prescolaire
from . import controles, dgess, esu, geographie, metadonnees, pdi
from .offre import lire_offre
from .outils import Journal


def _ecrire_couche(donnees: pd.DataFrame, chemin: Path, couche: str) -> None:
    if isinstance(donnees, gpd.GeoDataFrame):
        donnees.to_file(chemin, layer=couche, driver="GPKG", engine="pyogrio")
    else:
        pyogrio.write_dataframe(donnees, chemin, layer=couche, driver="GPKG")


def _ecrire_csv(donnees: pd.DataFrame, chemin: Path) -> None:
    table = pd.DataFrame(donnees.drop(columns="geometry", errors="ignore"))
    table.to_csv(chemin, sep=config.SEPARATEUR, encoding=config.ENCODAGE_SORTIE, index=False)


def executer_nettoyage(sortie: Path | None = None) -> dict[str, pd.DataFrame]:
    """Construit le référentiel, nettoie les tables DGESS, contrôle et écrit la base."""
    sortie = config.verifier_ecriture(Path(sortie or config.SORTIE_NETTOYAGE))
    sortie.mkdir(parents=True, exist_ok=True)
    journal = Journal()

    # Référentiel géographique et couches.
    communes = geographie.referentiel_communes(geographie.lire_communes())
    couches = geographie.couches(communes)
    alias = geographie.table_alias(communes)
    identifier = dgess.Identification(alias)

    # Tables DGESS.
    flux = dgess.lire_flux(identifier, journal)
    effectifs = dgess.lire_effectifs(identifier, journal)
    retenus = effectifs_retenus(effectifs)
    offre = lire_offre(identifier, journal)
    tableaux_dgess = principale.lire_base_principale(alias, journal)
    enf = enf_prescolaire.lire_enf(identifier, journal)
    prescolaire = enf_prescolaire.lire_prescolaire(identifier, alias, journal)
    vie = conditions_vie.construire(communes, alias, journal)

    # Rapports ESU et déplacés internes.
    esu_provinces, esu_totaux = esu.lire_esu(identifier, journal)
    esu_regions = esu.lire_esu_regions(identifier, journal)
    alias_provinces = {a.nom_normalise: a.pcode for a in alias.itertuples() if a.niveau == "province_ancienne"}
    deplaces = pdi.lire_pdi(communes, alias_provinces, journal)

    # Contrôles.
    base_principale = controles.effectifs_base_principale(alias)
    douteux = controles.repartition_sexes(retenus.rename(columns={"edition_retenue": "annee_publication"}))
    resultats_controles = {
        "completude_flux": controles.completude(flux, "annee_publication"),
        "completude_effectifs": controles.completude(effectifs, "annee_publication"),
        "coherence_sexes": controles.coherence_sexes(effectifs[effectifs["annee_scolaire"] >= "2015-2016"]),
        "repartition_sexes": douteux,
        "sommes_regions": controles.sommes_provinces_regions(effectifs, communes, base_principale),
        "sommes_nationales": controles.sommes_nationales(effectifs, base_principale),
        "jointure_contours_flux": controles.jointure_contours(flux, "annee_publication", communes),
        "jointure_contours_effectifs": controles.jointure_contours(effectifs, "annee_publication", communes),
    }
    resultats_controles["esu_totaux_primaire"] = esu.controle_totaux(esu_provinces, esu_totaux)
    resultats_controles["base_principale_unicite"] = principale.controle_unicite(tableaux_dgess)
    resultats_controles["base_principale_sommes"] = principale.controle_sommes(tableaux_dgess)
    resultats_controles["base_principale_sauts"] = principale.signaler_sauts(tableaux_dgess, journal)
    synthese = controles.synthese(resultats_controles)
    # Un rapport est jugé fiable au niveau provincial si la somme des provinces retrouve le total
    # primaire publié à 5 % près, pour les établissements comme pour les élèves.
    totaux = resultats_controles["esu_totaux_primaire"].copy()
    ecart_rel = pd.concat([
        (totaux["ecart_etablissements"] / totaux["etablissements_publie"]).abs(),
        (totaux["ecart_eleves"] / totaux["eleves_total_publie"]).abs(),
    ], axis=1).max(axis=1)
    totaux["rapport_fiable"] = ecart_rel.le(0.05)
    resultats_controles["esu_totaux_primaire"] = totaux
    fiables = set(zip(totaux.loc[totaux["rapport_fiable"], "source_fichier"], totaux.loc[totaux["rapport_fiable"], "type"]))
    esu_provinces["rapport_fiable"] = [(f, t) in fiables for f, t in
                                       zip(esu_provinces["source_fichier"], esu_provinces["type"])]
    retenus_esu = totaux[totaux["rapport_fiable"]]
    synthese = pd.concat([synthese, pd.DataFrame([
        {"controle": "esu_somme_provinces_egale_total_primaire_publie", "conforme": True,
         "detail": f"{len(retenus_esu)} tableaux sur {len(totaux)} retrouvent le total publié à 5 % près "
                   f"({', '.join(sorted(retenus_esu['mois'] + ' ' + retenus_esu['type']))}) ; "
                   "les autres sont marqués non fiables (rapport_fiable = faux)"},
        {"controle": "pdi_communes_rapprochees", "conforme": True,
         "detail": f"{deplaces['commune_pcode'].nunique()} communes, {deplaces['date_situation'].nunique()} dates "
                   f"de situation ({deplaces['date_situation'].min()} à {deplaces['date_situation'].max()})"},
        {"controle": "base_principale_lue_en_entier", "conforme": tableaux_dgess["tableau"].nunique() == 21,
         "detail": f"{tableaux_dgess['tableau'].nunique()} tableaux sur 21, {len(tableaux_dgess)} valeurs, "
                   f"{tableaux_dgess['feuille'].nunique()} feuilles"},
        {"controle": "base_principale_une_valeur_par_cle",
         "conforme": bool(resultats_controles["base_principale_unicite"]["conforme"].all()),
         "detail": f"{int(resultats_controles['base_principale_unicite']['doublons'].iloc[0])} doublons"},
        {"controle": "base_principale_sommes_coherentes",
         "conforme": bool(resultats_controles["base_principale_sommes"]["conforme"].all()),
         "detail": f"{int(resultats_controles['base_principale_sommes']['sommes_verifiees'].sum())} sommes vérifiées "
                   "(régions = national, garçons + filles = total, statuts, milieux et niveaux = total), "
                   f"{int(resultats_controles['base_principale_sommes']['sommes_en_ecart'].sum())} en écart"},
        {"controle": "base_principale_variations_brutales_signalees", "conforme": True,
         "detail": f"{len(resultats_controles['base_principale_sauts'])} comptages variant d'un facteur supérieur "
                   "à 2,5 d'une année à l'autre, consignés dans le journal sans correction "
                   "(surtout préscolaire, structures et salles)"},
        *[{"controle": nom, "conforme": conforme, "detail": detail} for nom, (conforme, detail) in
          enf_prescolaire.controler(enf, prescolaire, tableaux_dgess,
                                    dict(zip(communes["province_ancienne_pcode"],
                                             communes["region_ancienne_pcode"]))).items()],
        *[{"controle": nom, "conforme": bool(conforme), "detail": detail} for nom, (conforme, detail) in
          conditions_vie.controler(vie, communes, config.CONTROLE_PAUVRETE).items()],
        {"controle": "metadonnees_completes", "conforme": False, "detail": ""},
    ])], ignore_index=True)

    # Répartition par sexe invraisemblable : seul le total reste utilisable.
    cles_douteuses = set(zip(douteux["annee_scolaire"], douteux["entite_pcode"]))
    retenus["repartition_sexe_fiable"] = [
        (a, e) not in cles_douteuses for a, e in zip(retenus["annee_scolaire"], retenus["entite_pcode"])
    ]
    for annee, entite in sorted(cles_douteuses):
        journal.noter("fait_effectifs_retenus", "signalement", "répartition filles / garçons invraisemblable : "
                      "seul le total est utilisable", avant=f"{entite} {annee}")

    registre = pd.read_csv(config.SORTIE_COLLECTE / "registre_sources.csv", sep=config.SEPARATEUR,
                           dtype=str, encoding=config.ENCODAGE_SORTIE, keep_default_na=False)

    tables = {
        "commune": couches["commune"],
        "province": couches["province"],
        "region": couches["region"],
        "province_ancienne": couches["province_ancienne"],
        "region_ancienne": couches["region_ancienne"],
        "ref_alias_nom": alias,
        "fait_flux_publie": flux,
        "fait_effectifs_editions": effectifs,
        "fait_effectifs_retenus": retenus,
        "fait_offre_province": offre,
        "fait_base_principale": tableaux_dgess,
        "fait_enf_province": enf,
        "fait_prescolaire_province": prescolaire,
        "fait_conditions_vie": vie,
        "fait_esu_province": esu_provinces,
        "fait_esu_region": esu_regions,
        "fait_pdi_commune": deplaces,
        "meta_journal_nettoyage": journal.table(),
        "meta_controles": synthese,
        "meta_source": registre,
    }

    # Métadonnées : description des tables et dictionnaire des variables, puis leur contrôle.
    meta_tables, meta_variables = metadonnees.construire(tables)
    resultat = metadonnees.controle(meta_tables, meta_variables)
    ligne = synthese.index[synthese["controle"] == "metadonnees_completes"][0]
    synthese.loc[ligne, ["conforme", "detail"]] = [resultat["conforme"], resultat["detail"]]
    tables["meta_tables"] = meta_tables
    tables["meta_variables"] = meta_variables

    # Écriture : GeoPackage, CSV, contours légers pour le web.
    base = config.verifier_ecriture(config.BASE_GEOPACKAGE)
    base.unlink(missing_ok=True)
    for nom, donnees in tables.items():
        _ecrire_couche(donnees, base, nom)
        _ecrire_csv(donnees, sortie / f"{nom}.csv")
    for nom, detail in resultats_controles.items():
        _ecrire_csv(detail, sortie / f"controle_{nom}.csv")

    contours = geographie.ecrire_contours_web(couches, config.CONTOURS_WEB)
    _ecrire_csv(contours, sortie / "contours_web_bilan.csv")

    return {**tables, "controles_detail": resultats_controles, "contours_web": contours}
