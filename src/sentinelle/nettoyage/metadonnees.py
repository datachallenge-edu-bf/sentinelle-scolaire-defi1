"""Métadonnées de la base : description des tables et dictionnaire des variables.

Les deux tables sont produites à partir des tables réellement écrites : le nombre
de lignes, les colonnes et leurs types sont lus, seules les descriptions sont
rédigées ici. Une variable sans description est signalée par le contrôle.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

TABLES = {
    "commune": ("Contours et rattachements des 351 communes dans les deux découpages administratifs",
                "commune", "commune_pcode", "COD-AB (IGB, OCHA), août 2025 ; noms anciens : OpenStreetMap (HOT)", "2025"),
    "province": ("Contours des 47 provinces du découpage de juillet 2025, obtenus en regroupant les communes",
                 "province (découpage 2025)", "province_pcode", "COD-AB, août 2025", "2025"),
    "region": ("Contours des 17 régions du découpage de juillet 2025", "région (découpage 2025)", "region_pcode",
               "COD-AB, août 2025", "2025"),
    "province_ancienne": ("Contours des 45 provinces de l'ancien découpage, reconstitués à partir des anciens P-codes "
                          "des communes", "province (ancien découpage)", "province_ancienne_pcode", "COD-AB, août 2025",
                          "avant juillet 2025"),
    "region_ancienne": ("Contours des 13 régions de l'ancien découpage", "région (ancien découpage)",
                        "region_ancienne_pcode", "COD-AB, août 2025", "avant juillet 2025"),
    "ref_alias_nom": ("Correspondance entre les noms rencontrés dans les publications et les codes de l'ancien découpage",
                      "nom", "nom_normalise", "OpenStreetMap ; variantes relevées dans les annuaires DGESS", ""),
    "fait_flux_publie": ("Taux de promotion, de redoublement et d'abandon publiés par la DGESS",
                         "édition × entité × classe × sexe × indicateur",
                         "annee_publication, entite_pcode, niveau, sexe, indicateur",
                         "DGESS, annuaires statistiques du primaire, tableau I.8 (II.7 en 2017-2018)",
                         "éditions 2017-2018 à 2024-2025"),
    "fait_effectifs_editions": ("Effectifs et redoublants par classe et sexe, tels que publiés dans chaque édition "
                                "(historique sur une dizaine d'années par édition)",
                                "édition × année × entité × classe × sexe",
                                "annee_publication, annee_scolaire, entite_pcode, niveau, sexe",
                                "DGESS, annuaires statistiques du primaire, tableau VIII.3 (IX.3 en 2017-2018)",
                                "2007-2008 à 2024-2025"),
    "fait_effectifs_retenus": ("Effectifs et redoublants retenus : pour chaque année, la valeur de l'édition la plus "
                               "récente qui la donne", "année × entité × classe × sexe",
                               "annee_scolaire, entite_pcode, niveau, sexe",
                               "DGESS, annuaires statistiques du primaire, tableau VIII.3", "2007-2008 à 2024-2025"),
    "fait_esu_province": ("Écoles primaires fermées et rouvertes, élèves et enseignants concernés, par province",
                          "rapport mensuel × type × province", "mois, type, province_ancienne_pcode",
                          "ST-ESU, rapports statistiques mensuels (via ReliefWeb)", "novembre 2021 à novembre 2024"),
    "fait_esu_region": ("Établissements fermés (tous ordres), élèves et enseignants affectés, par région, "
                        "d'après le texte des rapports", "rapport mensuel × région", "mois, region_ancienne_pcode",
                        "ST-ESU, rapports statistiques mensuels (via ReliefWeb)", "novembre 2021 à mai 2023"),
    "fait_pdi_commune": ("Personnes déplacées internes accueillies, dont enfants, par commune",
                         "date de situation × commune", "date_situation, commune_pcode",
                         "SP/CONASUR, situations des personnes déplacées internes (via HDX)", "janvier 2019 à mars 2023"),
    "meta_tables": ("Description des tables de la base", "table", "table", "Sentinelle Scolaire", ""),
    "meta_variables": ("Dictionnaire des variables de la base", "table × variable", "table, variable",
                       "Sentinelle Scolaire", ""),
    "meta_journal_nettoyage": ("Journal des opérations de nettoyage : corrections, déductions, lignes écartées, "
                               "signalements", "opération", "", "Sentinelle Scolaire", ""),
    "meta_controles": ("Résultat des contrôles automatiques de la base", "contrôle", "controle",
                       "Sentinelle Scolaire", ""),
    "meta_source": ("Registre des sources de la collecte : fichier d'origine, pages, empreinte, URL",
                    "fichier source × jeu", "jeu, source_fichier", "Sentinelle Scolaire, étape 01", ""),
}

# Description, unité.
VARIABLES = {
    "commune_pcode": ("P-code de la commune (découpage 2025)", ""),
    "commune_nom": ("Nom de la commune (COD-AB)", ""),
    "commune_ancienne_pcode": ("P-code de la commune dans l'ancien découpage", ""),
    "province_pcode": ("P-code de la province (découpage 2025)", ""),
    "province_nom": ("Nom de la province (découpage 2025)", ""),
    "region_pcode": ("P-code de la région (découpage 2025)", ""),
    "region_nom": ("Nom de la région (découpage 2025)", ""),
    "province_ancienne_pcode": ("P-code de la province dans l'ancien découpage (45 provinces)", ""),
    "province_ancienne_nom": ("Nom de la province dans l'ancien découpage", ""),
    "region_ancienne_pcode": ("P-code de la région dans l'ancien découpage (13 régions)", ""),
    "region_ancienne_nom": ("Nom de la région dans l'ancien découpage", ""),
    "province_ancienne_partagee": ("Vrai si l'ancienne province a été scindée entre plusieurs provinces en 2025 "
                                   "(Soum, Tapoa)", "booléen"),
    "provinces_actuelles": ("P-codes des provinces de 2025 issues de l'ancienne province", ""),
    "superficie_km2": ("Superficie", "km²"),
    "nb_communes": ("Nombre de communes", "communes"),
    "latitude": ("Latitude du centre de la commune, calculé en projection UTM 30N", "degrés"),
    "longitude": ("Longitude du centre de la commune, calculé en projection UTM 30N", "degrés"),
    "geometry": ("Contour (WGS 84)", ""),
    "nom_normalise": ("Nom en majuscules, sans accent, espace ni ponctuation", ""),
    "pcode": ("P-code de l'entité désignée par le nom", ""),
    "niveau": ("Niveau : classe (CP1 à CM2, Total) dans les tables de faits ; niveau géographique dans l'alias", ""),
    "nom_reference": ("Nom de référence de l'entité", ""),
    "origine": ("Origine de l'alias", ""),
    "annee_publication": ("Édition de l'annuaire dont provient la valeur (année scolaire)", ""),
    "edition_retenue": ("Édition de l'annuaire dont la valeur est retenue (la plus récente)", ""),
    "annee_scolaire": ("Année scolaire à laquelle se rapporte la valeur", ""),
    "entite_pcode": ("P-code de l'entité de l'ancien découpage (province, région, ou BF pour le pays)", ""),
    "niveau_geo": ("Niveau géographique de l'entité", ""),
    "nom_source": ("Nom de l'entité tel qu'écrit dans la source", ""),
    "sexe": ("Sexe : G (garçons), F (filles), T (total)", ""),
    "indicateur": ("Indicateur de flux : promotion, redoublement ou abandon", ""),
    "valeur_pct": ("Taux publié ; les valeurs négatives sont ramenées à zéro par la DGESS", "%"),
    "effectif": ("Nombre d'élèves inscrits", "élèves"),
    "redoublants": ("Nombre d'élèves redoublants", "élèves"),
    "repartition_sexe_fiable": ("Faux si le rapport filles / garçons de l'année est invraisemblable : "
                                "seul le total est alors utilisable", "booléen"),
    "source_fichier": ("Fichier d'origine remis par les organisateurs", ""),
    "page": ("Page du fichier d'origine", ""),
    "mois": ("Mois du rapport (AAAA-MM ou AAAA-MM-JJ)", ""),
    "type": ("Type de situation : établissements fermés ou rouverts", ""),
    "etablissements": ("Nombre d'établissements primaires", "établissements"),
    "eleves_filles": ("Élèves concernés, filles", "élèves"),
    "eleves_garcons": ("Élèves concernés, garçons", "élèves"),
    "eleves_total": ("Élèves concernés, total", "élèves"),
    "enseignants_femmes": ("Enseignants concernés, femmes", "enseignants"),
    "enseignants_hommes": ("Enseignants concernés, hommes", "enseignants"),
    "enseignants_total": ("Enseignants concernés, total", "enseignants"),
    "ligne_coherente": ("Vrai si filles + garçons = total et femmes + hommes = total", "booléen"),
    "rapport_fiable": ("Vrai si, pour ce rapport, la somme des provinces retrouve le total primaire publié à 5 % près", "booléen"),
    "methode_lecture": ("Mode de lecture du rapport : texte natif ou reconnaissance de caractères (à vérifier)", ""),
    "etablissements_fermes": ("Établissements fermés, tous ordres d'enseignement", "établissements"),
    "eleves_affectes": ("Élèves affectés par les fermetures", "élèves"),
    "eleves_affectes_filles": ("Élèves affectés par les fermetures, dont filles", "élèves"),
    "enseignants_affectes": ("Enseignants affectés par les fermetures", "enseignants"),
    "date_situation": ("Date de la situation des déplacés", ""),
    "pdi_total": ("Personnes déplacées internes accueillies dans la commune", "personnes"),
    "pdi_enfants": ("Enfants parmi les déplacés ; vide avant septembre 2021, non recensés séparément", "personnes"),
    "source_csv_pack": ("Fichier CSV du Data Pack dont provient la valeur", ""),
    "table": ("Nom de la table", ""),
    "description": ("Description", ""),
    "grain": ("Ce que représente une ligne", ""),
    "cle": ("Colonnes qui identifient une ligne", ""),
    "sources": ("Sources des données", ""),
    "periode": ("Période couverte", ""),
    "nb_lignes": ("Nombre de lignes", "lignes"),
    "nb_colonnes": ("Nombre de colonnes", "colonnes"),
    "date_production": ("Date de production de la table", ""),
    "variable": ("Nom de la variable", ""),
    "type_donnee": ("Type de donnée", ""),
    "unite": ("Unité", ""),
    "operation": ("Opération de nettoyage", ""),
    "motif": ("Motif de l'opération", ""),
    "ligne": ("Ligne du fichier d'origine", ""),
    "valeur_avant": ("Valeur ou texte avant l'opération", ""),
    "valeur_apres": ("Valeur après l'opération", ""),
    "controle": ("Nom du contrôle", ""),
    "conforme": ("Vrai si le contrôle est satisfait", "booléen"),
    "detail": ("Détail du résultat", ""),
    "jeu": ("Jeu de données de la collecte", ""),
    "libelle": ("Libellé du jeu", ""),
    "theme": ("Thème du jeu", ""),
    "source_chemin": ("Chemin du fichier d'origine", ""),
    "regle": ("Règle de sélection des pages", ""),
    "pages_retenues": ("Pages extraites", ""),
    "nb_pages": ("Nombre de pages extraites", "pages"),
    "sha256_source": ("Empreinte SHA-256 du fichier d'origine", ""),
    "sha256_csv_pack": ("Empreinte SHA-256 du CSV du Data Pack", ""),
    "producteur": ("Producteur de la donnée", ""),
    "description_source": ("Description de la source d'après le manifeste du Data Pack", ""),
    "url": ("Adresse de téléchargement d'origine", ""),
    "date_collecte": ("Date de la collecte", ""),
    "usage": ("Usage prévu dans Sentinelle Scolaire", ""),
}


def _type(serie: pd.Series) -> str:
    if serie.name == "geometry":
        return "géométrie"
    if pd.api.types.is_bool_dtype(serie):
        return "booléen"
    if pd.api.types.is_integer_dtype(serie):
        return "entier"
    if pd.api.types.is_float_dtype(serie):
        return "décimal"
    return "texte"


def construire(tables: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tables meta_tables et meta_variables pour les tables fournies, y compris elles-mêmes."""
    aujourd_hui = date.today().isoformat()
    variables = []
    for nom, donnees in tables.items():
        for colonne in donnees.columns:
            description, unite = VARIABLES.get(colonne, ("", ""))
            variables.append({"table": nom, "variable": colonne, "type_donnee": _type(donnees[colonne]),
                              "unite": unite, "description": description})
    meta_variables = pd.DataFrame(variables)
    for colonne in ["table", "variable", "type_donnee", "unite", "description"]:
        meta_variables = pd.concat([meta_variables, pd.DataFrame([{
            "table": "meta_variables", "variable": colonne, "type_donnee": "texte",
            "unite": VARIABLES[colonne][1], "description": VARIABLES[colonne][0]}])], ignore_index=True)

    colonnes_meta_tables = ["table", "description", "grain", "cle", "sources", "periode", "nb_lignes",
                            "nb_colonnes", "date_production"]
    lignes = []
    for nom, donnees in {**tables, "meta_variables": meta_variables}.items():
        description, grain, cle, sources, periode = TABLES.get(nom, ("", "", "", "", ""))
        lignes.append({"table": nom, "description": description, "grain": grain, "cle": cle, "sources": sources,
                       "periode": periode, "nb_lignes": len(donnees), "nb_colonnes": donnees.shape[1],
                       "date_production": aujourd_hui})
    description, grain, cle, sources, periode = TABLES["meta_tables"]
    lignes.append({"table": "meta_tables", "description": description, "grain": grain, "cle": cle,
                   "sources": sources, "periode": periode, "nb_lignes": len(lignes) + 1,
                   "nb_colonnes": len(colonnes_meta_tables), "date_production": aujourd_hui})
    meta_tables = pd.DataFrame(lignes, columns=colonnes_meta_tables)
    for colonne in colonnes_meta_tables:
        meta_variables = pd.concat([meta_variables, pd.DataFrame([{
            "table": "meta_tables", "variable": colonne, "type_donnee": _type(meta_tables[colonne]),
            "unite": VARIABLES[colonne][1], "description": VARIABLES[colonne][0]}])], ignore_index=True)
    return meta_tables, meta_variables


def controle(meta_tables: pd.DataFrame, meta_variables: pd.DataFrame) -> dict:
    sans_variable = meta_variables[meta_variables["description"] == ""]
    sans_table = meta_tables[meta_tables["description"] == ""]
    manquants = [f"{r.table}.{r.variable}" for r in sans_variable.itertuples()] + list(sans_table["table"])
    return {"controle": "metadonnees_completes", "conforme": not manquants,
            "detail": "toutes les tables et variables sont décrites" if not manquants
            else "sans description : " + ", ".join(manquants)}
