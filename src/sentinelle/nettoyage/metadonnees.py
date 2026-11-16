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
    "fait_offre_province": ("Écoles, salles, groupes pédagogiques, maîtres et élèves par province et statut, avec les "
                            "élèves par maître et par salle", "année × entité × statut",
                            "annee_scolaire, entite_pcode, statut",
                            "DGESS, annuaires statistiques du primaire, tableau I.1 (II.1 en 2017-2018)",
                            "2017-2018 à 2024-2025"),
    "fait_base_principale": ("Tous les tableaux de la base principale DGESS : effectifs du préscolaire et du primaire "
                             "par région, statut, milieu, niveau et sexe, nouveaux inscrits au CP1, TBA, TBS, taux "
                             "d'achèvement, réussite au CEP, indices de parité, écoles, structures et salles du "
                             "préscolaire", "tableau × entité × statut × milieu × classe × sexe × année",
                             "tableau, entite_pcode, statut, milieu, classe, sexe, annee_scolaire",
                             "DGESS, base principale « Données statistiques préscolaire et primaire 2016-2025 » "
                             "(14 feuilles, 21 tableaux)", "2015-2016 à 2024-2025"),
    "fait_enf_province": ("Éducation non formelle : centres et apprenants (adultes 1er et 2nd cycle, adolescents), "
                          "par province et milieu", "campagne × entité × milieu", "campagne, entite_pcode, milieu",
                          "DGESS, annuaires de l'éducation non formelle, tableaux 1.1 et 1.3",
                          "campagnes 2018, 2019, 2020 et 2024"),
    "fait_prescolaire_province": ("Préscolaire : population préscolarisable, enfants préscolarisés, taux de "
                                  "préscolarisation et enfants inscrits par section, par province et sexe",
                                  "année × entité × sexe", "annee_scolaire, entite_pcode, sexe",
                                  "DGESS, annuaires du préscolaire, tableaux 02 et 9 (11 en 2023-2024)",
                                  "2023-2024 et 2024-2025"),
    "fait_conditions_vie": ("Pauvreté, emploi, scolarisation, enfants hors de l'école, alphabétisation, mariage précoce, "
                            "actes de naissance, eau, électricité, téléphone, par commune, province, région et pour "
                            "le pays", "entité (commune, province, région, pays)", "niveau_geo, entite_pcode",
                            "INSD, 5e RGPH, volume 3, Mesure et cartographie de la pauvreté (novembre 2022), annexes "
                            "4 à 9 ; EHCVM 2018 et RGPH 2019", "2019"),
    "fait_conditions_scolarisation": ("Conditions de scolarisation par province : équipement des écoles, distance "
                                      "parcourue, taille des écoles, logements de maîtres, manuels, mobilier, "
                                      "profession des parents, surface, ancienneté et état des salles, TBA, TBS, TNS, "
                                      "achèvement, CEP", "édition × section × sous-tableau × province × variable",
                                      "annee_scolaire, section, sous_tableau, entite_pcode, variable",
                                      "DGESS, annuaires statistiques du primaire, sections I à X selon les éditions",
                                      "2017-2018 à 2024-2025"),
    "fait_profils_pauvrete": ("Consommation par personne, sévérité de la pauvreté et inégalités (Gini, Theil, rapports "
                              "interdéciles) par province et commune, pour 10 régions ; l'incidence et la profondeur "
                              "reprennent celles du RGPH 2019", "entité (province, commune)", "niveau_geo, entite_pcode",
                              "INSD, profils régionaux de pauvreté (octobre 2023), à partir de l'EHCVM 2018 et du RGPH 2019",
                              "2019 (année de référence)"),
    "fait_repartitions_province": ("Élèves et nouveaux entrants au CP1 par âge et sexe ; enseignants par sexe, âge et "
                                   "années d'expérience ; par province", "édition × section × sous-tableau × province "
                                   "× modalité × variable", "annee_scolaire, section, sous_tableau, entite_pcode, "
                                   "modalite, variable", "DGESS, annuaires statistiques du primaire, répartitions par âge "
                                   "et personnel enseignant", "2017-2018 à 2024-2025"),
    "fait_causes_abandon": ("Abandons déclarés pour orpaillage, mariage et grossesse, par région et pour le pays ; "
                            "primaire et post-primaire", "année × ordre × entité", "annee_scolaire, ordre, entite_pcode",
                            "DGESS, tableaux de bord de l'enseignement primaire (éditions 2017-2018 à 2023-2024) et du "
                            "post-primaire et secondaire (2023, 2024)", "2016-2017 à 2022-2023"),
    "fait_secondaire_province": ("Post-primaire et secondaire par province, région et pays : TBA en 6e et en 2nde, "
                                 "TBS et taux nets (12-15, 16-18, 12-18 ans), taux d'achèvement, avec population "
                                 "et effectif, et taux de flux par classe de la 6e à la terminale",
                                 "année × entité × indicateur × mesure × sexe",
                                 "annee_scolaire, entite_pcode, indicateur, mesure, sexe",
                                 "DGESS, annuaires statistiques du post-primaire et du secondaire 2018-2019 à 2022-2023 (2019-2020 du Data Pack, les autres fournis par l'équipe) ; flux de 2019-2020 non lus (pages pivotées dans la conversion du Data Pack)",
                                 "2018-2019 à 2022-2023"),
    "fait_secondaire_region": ("Conditions d'accueil du post-primaire et du secondaire général public par région : "
                               "commodités des établissements, état des salles, ratio élèves par classe",
                               "année × région × tableau × indicateur", "annee_scolaire, entite_pcode, tableau, indicateur",
                               "DGESS, annuaires statistiques du post-primaire et du secondaire 2018-2019 à 2022-2023 (2019-2020 du Data Pack, les autres fournis par l'équipe)", "2018-2019 à 2022-2023"),
    "fait_tableau_bord_secondaire": ("Indicateurs du post-primaire et du secondaire par région et pour le pays : "
                                     "élèves, TBA, TBS, taux d'achèvement, par sexe",
                                     "année × entité × ordre × indicateur × sexe",
                                     "annee_scolaire, entite_pcode, ordre, indicateur, sexe",
                                     "DGESS, tableaux de bord du post-primaire et du secondaire 2023 et 2024 (Data Pack), "
                                     "2025 (fourni par l'équipe) : pages régionales et table nationale des indicateurs clés",
                                     "2020-2021 à 2024-2025"),
    "fait_insd_commune": ("Écoles, salles, salles sous paillote, écoles fermées, élèves et enseignants du primaire ; "
                          "élèves du post-primaire et du secondaire général, par commune",
                          "année × commune × indicateur × modalité", "annee_scolaire, commune_pcode, indicateur, modalite",
                          "INSD, annuaires statistiques régionaux 2024 (13 régions, dont 3 téléchargées sur insd.bf)", "2014-2015 à 2023-2024"),
    "fait_population": ("Population par âge simple (0 à 79 ans, 80 = 80 ans et plus) et sexe : communes et provinces "
                        "de 2025, régions et pays", "année × niveau × entité × âge × sexe",
                        "annee, niveau_geo, entite_pcode, age, sexe", "INSD, projections de population actualisées par âge simple (portail OpenDataForAfrica), découpage de 2025 ; anciennes projections nationales 2007-2018",
                        "2007-2018 (pays), 2020-2025 (communes), 2020-2035 (provinces, régions, pays)"),
    "fait_mines_region": ("Permis d'exploitation et sites miniers par typologie (industrielle, semi-mécanisée, "
                          "artisanale), par région ; série lacunaire conservée pour mémoire",
                          "année × région × indicateur × typologie", "annee, entite_pcode, indicateur, typologie",
                          "INSD, annuaires statistiques régionaux 2024 (sources DGCM, MEMC)", "2014 à 2024 selon les régions"),
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
    "niveau": ("Niveau : classe (CP1 à CM2, Total) dans les tables de faits ; niveau géographique (region, pays) "
               "dans l'alias et les tableaux de bord", ""),
    "nom_reference": ("Nom de référence de l'entité", ""),
    "origine": ("Origine de l'alias", ""),
    "annee_publication": ("Édition de l'annuaire dont provient la valeur (année scolaire)", ""),
    "edition_retenue": ("Édition de l'annuaire dont la valeur est retenue (la plus récente)", ""),
    "annee_scolaire": ("Année scolaire à laquelle se rapporte la valeur", ""),
    "entite_pcode": ("P-code de l'entité de l'ancien découpage (province, région, ou BF pour le pays)", ""),
    "niveau_geo": ("Niveau géographique de l'entité", ""),
    "nom_source": ("Nom de l'entité tel qu'écrit dans la source", ""),
    "sexe": ("Sexe : G (garçons), F (filles), T (total ou ensemble)", ""),
    "indicateur": ("Indicateur : promotion, redoublement ou abandon (flux publiés) ; effectifs, TBA, TBS, "
                   "taux d'achèvement, réussite au CEP, indices de parité, écoles, structures, salles "
                   "(base principale) ; permis ou sites (mines) ; tba_6e, tba_2nde, tbs_* et tns_* (post_primaire, "
                   "secondaire, ensemble), tach_post_primaire, tach_secondaire, flux_6e à flux_tle "
                   "(fait_secondaire_province) ; commodités, état des salles, ratios (fait_secondaire_region) ; "
                   "eleves, tba, tbs, taux_achevement (fait_tableau_bord_secondaire)", ""),
    "valeur": ("Valeur publiée, dans l'unité indiquée", ""),
    "modalite": ("Modalité : F (filles ou femmes), G (garçons ou hommes), T (ensemble), public, prive, communautaire", ""),
    "age": ("Âge révolu en années (80 = 80 ans et plus)", "années"),
    "population": ("Effectif de la population", "personnes"),
    "mesure": ("Mesure : population de référence, effectif au numérateur, taux, indice de parité (indicateurs) ; "
               "promotion, redoublement, abandon (flux, en %)", ""),
    "incidence": ("Part de la population sous le seuil de pauvreté (P0)", "%"),
    "contribution": ("Contribution de l'entité à la pauvreté de la région (C0)", "%"),
    "profondeur": ("Écart moyen au seuil de pauvreté (P1)", "%"),
    "severite": ("Sévérité de la pauvreté (P2) ; publiée seulement dans certains profils", "%"),
    "consommation_par_personne": ("Consommation annuelle moyenne par personne", "FCFA"),
    "gini": ("Indice de Gini de la consommation (0 = égalité parfaite)", "indice"),
    "theil_0": ("Indice de Theil (0) de la consommation", "indice"),
    "theil_1": ("Indice de Theil (1) de la consommation", "indice"),
    "rapport_q90_q10": ("Rapport entre le 9e et le 1er décile de consommation", "rapport"),
    "rapport_q90_q50": ("Rapport entre le 9e décile et la médiane de consommation", "rapport"),
    "modalite": ("Ligne du tableau : F (filles ou femmes), G (garçons), H (hommes), T (total), pct (pourcentage)", ""),
    "abandons_orpaillage": ("Abandons déclarés pour cause d'orpaillage", "élèves"),
    "abandons_mariage": ("Abandons déclarés pour cause de mariage", "élèves"),
    "abandons_grossesse": ("Abandons déclarés pour cause de grossesse", "élèves"),
    "abandons_trois_causes": ("Abandons déclarés pour orpaillage, mariage ou grossesse", "élèves"),
    "annee": ("Année civile (permis et sites miniers)", "année"),
    "typologie": ("Typologie d'exploitation minière : industrielle, semi_mecanisee, artisanale, ensemble", ""),
    "section": ("Section de l'annuaire : equipement, distance, taille_ecoles, logements_maitres, manuels, mobilier, "
                "profession_parents, surface_salles, anciennete_salles, murs, toitures, tba, tbs, tns, achevement, cep ; "
                "ages_eleves, ages_entrants, enseignants (répartitions)", ""),
    "sous_tableau": ("Sous-tableau de la section : public, prive, ensemble, urbain ou rural", ""),
    "code_rgph": ("Code de l'entité dans le RGPH 2019 ; plusieurs codes quand des arrondissements sont regroupés", ""),
    "nb_unites_rgph": ("Nombre d'unités du RGPH regroupées dans la ligne (arrondissements de Ouagadougou et de Bobo-Dioulasso)", "unités"),
    "annee_reference": ("Année de référence des indicateurs", "année"),
    "population": ("Population résidente au recensement", "personnes"),
    "menages": ("Ménages au recensement", "ménages"),
    "incidence_pauvrete": ("Part de la population sous le seuil de pauvreté (P0)", "%"),
    "profondeur_pauvrete": ("Écart moyen au seuil de pauvreté (P1)", "%"),
    "nombre_pauvres": ("Personnes pauvres", "personnes"),
    "emploi_7_14": ("Enfants de 7 à 14 ans occupés (travail des enfants)", "%"),
    "emploi_15_24": ("Jeunes de 15 à 24 ans occupés", "%"),
    "emploi_25_64": ("Adultes de 25 à 64 ans occupés", "%"),
    "chomage_15_24": ("Chômage des 15-24 ans", "%"),
    "chomage_25_64": ("Chômage des 25-64 ans", "%"),
    "travailleurs_autonomes_15_24": ("Travailleurs autonomes parmi les 15-24 ans occupés", "%"),
    "travailleurs_autonomes_25_64": ("Travailleurs autonomes parmi les 25-64 ans occupés", "%"),
    "frequentation_postprimaire": ("Taux net de fréquentation du post-primaire", "%"),
    "frequentation_lycee": ("Taux net de fréquentation du lycée", "%"),
    "ratio_filles_garcons_primaire": ("Rapport filles / garçons scolarisés au primaire", "rapport"),
    "ratio_filles_garcons_post_primaire": ("Rapport filles / garçons scolarisés au post-primaire", "rapport"),
    "ratio_filles_garcons_secondaire": ("Rapport filles / garçons scolarisés au secondaire", "rapport"),
    "hors_ecole_6_11": ("Enfants de 6 à 11 ans hors de l'école", "%"),
    "hors_ecole_12_15": ("Enfants de 12 à 15 ans hors de l'école", "%"),
    "hors_ecole_16_18": ("Jeunes de 16 à 18 ans hors de l'école", "%"),
    "ni_ecole_ni_travail_15_24": ("Jeunes de 15 à 24 ans ni à l'école ni au travail", "%"),
    "alphabetisation_15_64": ("Alphabétisation des 15-64 ans", "%"),
    "dependance_demographique": ("Rapport de dépendance démographique", "%"),
    "filles_17_ans_mariees": ("Filles de 17 ans mariées", "%"),
    "acte_naissance": ("Personnes disposant d'un acte de naissance", "%"),
    "sanitaires_ameliores": ("Ménages disposant de sanitaires améliorés", "%"),
    "eau_amelioree": ("Ménages accédant à une eau améliorée", "%"),
    "electricite": ("Ménages accédant à l'électricité", "%"),
    "energie_cuisson_amelioree": ("Ménages utilisant une énergie de cuisson améliorée", "%"),
    "telephone": ("Ménages accédant à un téléphone", "%"),
    "valeurs_hors_domaine": ("Indicateurs dont la valeur publiée sort de son domaine (taux > 100, rapport > 3), conservés tels quels", ""),
    "campagne": ("Campagne d'éducation non formelle, lue dans l'en-tête des pages de l'annuaire", "année"),
    "centres_adultes": ("Centres d'éducation non formelle des adultes", "centres"),
    "centres_adolescents": ("Centres d'éducation non formelle des adolescents (CEBNF et assimilés)", "centres"),
    "centres_total": ("Centres d'éducation non formelle", "centres"),
    "apprenants_total": ("Apprenants de l'éducation non formelle (tableau 1.1)", "apprenants"),
    "apprenants_femmes": ("Apprenantes de l'éducation non formelle (tableau 1.1)", "apprenants"),
    "adultes_1er_cycle": ("Apprenants adultes du 1er cycle (alphabétisation initiale)", "apprenants"),
    "adultes_1er_cycle_femmes": ("Apprenants adultes du 1er cycle, dont femmes", "apprenants"),
    "adultes_2nd_cycle": ("Apprenants adultes du 2nd cycle", "apprenants"),
    "adultes_2nd_cycle_femmes": ("Apprenants adultes du 2nd cycle, dont femmes", "apprenants"),
    "adultes_total": ("Apprenants adultes, 1er et 2nd cycle", "apprenants"),
    "adultes_total_femmes": ("Apprenants adultes, dont femmes", "apprenants"),
    "adolescents": ("Apprenants adolescents de l'éducation non formelle (enfants non scolarisés ou déscolarisés)",
                    "apprenants"),
    "adolescents_filles": ("Apprenants adolescents, dont filles", "apprenants"),
    "apprenants_total_t13": ("Apprenants de l'éducation non formelle (tableau 1.3, contrôle du tableau 1.1)",
                             "apprenants"),
    "apprenants_femmes_t13": ("Apprenantes (tableau 1.3, contrôle du tableau 1.1)", "apprenants"),
    "population_prescolarisable": ("Enfants d'âge préscolaire (3 à 5 ans) projetés", "enfants"),
    "enfants_prescolarises": ("Enfants inscrits au préscolaire (tableau 02)", "enfants"),
    "taux_prescolarisation": ("Enfants préscolarisés rapportés à la population préscolarisable, tel que publié", "%"),
    "petite_section": ("Enfants inscrits en petite section", "enfants"),
    "moyenne_section": ("Enfants inscrits en moyenne section", "enfants"),
    "grande_section": ("Enfants inscrits en grande section, futurs entrants au CP1", "enfants"),
    "enfants_inscrits": ("Enfants inscrits au préscolaire (tableau 9, contrôle du tableau 02)", "enfants"),
    "tableau": ("Feuille et numéro du tableau dans la base principale", ""),
    "ordre": ("Ordre d'enseignement : prescolaire, primaire, post_primaire ou secondaire", ""),
    "milieu": ("Milieu : urbain, rural, indetermine ou total", ""),
    "classe": ("Classe : CP1 à CM2, petite, moyenne ou grande section, ou total", ""),
    "feuille": ("Feuille du classeur d'origine", ""),
    "titre": ("Titre du tableau dans le classeur d'origine", ""),
    "valeur_pct": ("Taux publié ; les valeurs négatives sont ramenées à zéro par la DGESS", "%"),
    "effectif": ("Nombre d'élèves inscrits", "élèves"),
    "redoublants": ("Nombre d'élèves redoublants", "élèves"),
    "repartition_sexe_fiable": ("Faux si le rapport filles / garçons de l'année est invraisemblable : "
                                "seul le total est alors utilisable", "booléen"),
    "source_fichier": ("Fichier d'origine remis par les organisateurs", ""),
    "statut": ("Statut des écoles : public, prive, communautaire (préscolaire) ou total", ""),
    "ecoles": ("Nombre d'écoles primaires", "écoles"),
    "salles": ("Nombre de salles de classe", "salles"),
    "groupes_pedagogiques": ("Nombre de groupes pédagogiques", "groupes"),
    "maitres": ("Nombre de maîtres chargés de cours", "maîtres"),
    "eleves": ("Nombre d'élèves", "élèves"),
    "eleves_par_maitre_publie": ("Élèves par maître, tel que publié", "élèves par maître"),
    "eleves_par_maitre": ("Élèves par maître, recalculé", "élèves par maître"),
    "eleves_par_salle": ("Élèves par salle de classe, recalculé", "élèves par salle"),
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
    "variable": ("Nom de la variable (dictionnaire) ou de la colonne du tableau d'origine (conditions de "
                 "scolarisation : nombre d'écoles, de salles, part d'élèves, taux...)", ""),
    "type_donnee": ("Type de donnée", ""),
    "unite": ("Unité : nombre, pour cent ou indice (rapport filles / garçons)", ""),
    "operation": ("Opération de nettoyage", ""),
    "motif": ("Motif de l'opération", ""),
    "ligne": ("Ligne du fichier d'origine", ""),
    "valeur_avant": ("Valeur ou texte avant l'opération", ""),
    "valeur_apres": ("Valeur après l'opération", ""),
    "controle": ("Nom du contrôle", ""),
    "conforme": ("Vrai si le contrôle est satisfait", "booléen"),
    "detail": ("Détail du résultat", ""),
    "jeu": ("Jeu de données de la collecte", ""),
    "libelle": ("Libellé : nom du jeu de données (registre des sources) ou de l'entité dans la publication (conditions de vie)", ""),
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
