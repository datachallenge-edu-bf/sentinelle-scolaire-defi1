"""Étape 03 : transformation des tables nettoyées en tables d'analyse."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from .. import config
from . import metadonnees_modele
from . import decoupage_2025, demographie, nommage, recensement
from .fiche import FICHES
from .panel import (SEUIL_RUPTURE, construire_panel, construire_panel_mensuel, construire_panel_region,
                    construire_serie_nationale)

SORTIE = config.DONNEES / "03_transformation"

# Rôle, description, source de chaque variable de la table d'analyse.
VARIABLES = {
    "population_totale": ('explicative', "Population totale de l'unité, année t", 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "moins_15": ('explicative', 'Population de moins de 15 ans', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "age_15_64": ('explicative', 'Population de 15 à 64 ans', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "plus_64": ('explicative', 'Population de 65 ans et plus', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "enfants_3_5": ('explicative', 'Enfants de 3 à 5 ans (âge du préscolaire)', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "enfants_5": ('explicative', "Enfants de 5 ans (entrants potentiels au CP1 l'année suivante)", 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "enfants_6_11": ('explicative', 'Enfants de 6 à 11 ans (âge du primaire)', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "enfants_6_11_filles": ('explicative', 'Filles de 6 à 11 ans', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "enfants_6_11_garcons": ('explicative', 'Garçons de 6 à 11 ans', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "enfants_12_15": ('explicative', 'Enfants de 12 à 15 ans (âge du post-primaire)', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "enfants_12_15_filles": ('explicative', 'Filles de 12 à 15 ans', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "enfants_12_15_garcons": ('explicative', 'Garçons de 12 à 15 ans', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "jeunes_16_18": ('explicative', 'Jeunes de 16 à 18 ans (âge du secondaire)', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "methode_population": ('identifiant', 'Méthode de la population : projection publiée ou rétroprojection par cohortes (avant 2020)', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "rapport_dependance": ('explicative', 'Moins de 15 ans et 65 ans et plus pour 100 personnes de 15 à 64 ans', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "part_moins_15": ('explicative', 'Part des moins de 15 ans dans la population, en %', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "croissance_enfants_6_11": ('explicative', 'Croissance des enfants de 6 à 11 ans depuis t-1, en %', 'INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "commune_pcode": ('identifiant', 'Code de la commune (découpage de 2025)', 'COD-AB'),
    "commune_nom": ('identifiant', 'Nom de la commune', 'COD-AB'),
    "eleves_primaire_insd": ('explicative', 'Élèves du primaire de la commune', 'INSD, annuaires statistiques régionaux 2024'),
    "enseignants_primaire_insd": ('explicative', 'Enseignants du primaire de la commune', 'INSD, annuaires statistiques régionaux 2024'),
    "salles_primaire_insd": ('explicative', 'Salles de classe du primaire de la commune', 'INSD, annuaires statistiques régionaux 2024'),
    "salles_primaire_paillote_insd": ('explicative', 'Salles du primaire sous paillote', 'INSD, annuaires statistiques régionaux 2024'),
    "ecoles_primaires_fermees_insd": ('explicative', 'Écoles primaires fermées pour insécurité', 'INSD, annuaires statistiques régionaux 2024'),
    "eleves_post_primaire_insd": ('explicative', 'Élèves du post-primaire (enseignement général) de la commune', 'INSD, annuaires statistiques régionaux 2024'),
    "tbs_primaire_commune": ('explicative', 'Taux brut de scolarisation du primaire de la commune, en %', 'INSD, annuaires statistiques régionaux 2024 ; INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "tbs_post_primaire_commune": ('explicative', 'Taux brut de scolarisation du post-primaire de la commune, en %', 'INSD, annuaires statistiques régionaux 2024 ; INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "eleves_par_enseignant_primaire_insd": ('explicative', 'Élèves par enseignant du primaire de la commune', 'INSD, annuaires statistiques régionaux 2024'),
    "part_salles_primaire_paillote_insd": ('explicative', 'Part des salles du primaire sous paillote', 'INSD, annuaires statistiques régionaux 2024'),
    "deplaces_pour_100_habitants": ('explicative', 'Déplacés internes pour 100 habitants de la commune', 'CONASUR ; INSD, projections de population actualisées par âge simple (OpenDataForAfrica)'),
    "evolution_eleves_primaire_insd": ('explicative', 'Évolution des élèves du primaire de la commune depuis t-1, en %', 'INSD, annuaires statistiques régionaux 2024'),
    "pauvrete_commune_2019": ('explicative', 'Incidence de la pauvreté de la commune (2019)', 'INSD, RGPH 2019'),
    "hors_ecole_6_11_commune_2019": ('explicative', "Enfants de 6 à 11 ans hors de l'école (2019)", 'INSD, RGPH 2019'),
    "hors_ecole_12_15_commune_2019": ('explicative', "Enfants de 12 à 15 ans hors de l'école (2019)", 'INSD, RGPH 2019'),
    "filles_17_ans_mariees_commune_2019": ('explicative', 'Filles de 17 ans mariées (2019)', 'INSD, RGPH 2019'),
    "alphabetisation_adultes_commune_2019": ('explicative', 'Alphabétisation des 15-64 ans (2019)', 'INSD, RGPH 2019'),
    "electricite_commune_2019": ('explicative', "Ménages ayant l'électricité (2019)", 'INSD, RGPH 2019'),
    "travail_enfants_7_14_commune_2019": ('explicative', 'Enfants de 7 à 14 ans qui travaillent (2019)', 'INSD, RGPH 2019'),
    "province_ancienne_pcode": ("identifiant", "Code de la province (ancien découpage, 45 provinces)", "COD-AB"),
    "province_ancienne_nom": ("identifiant", "Nom de la province", "OpenStreetMap (HOT)"),
    "region_ancienne_pcode": ("identifiant", "Code de la région (ancien découpage)", "COD-AB"),
    "region_ancienne_nom": ("identifiant", "Nom de la région", "OpenStreetMap (HOT)"),
    "provinces_actuelles": ("identifiant", "Provinces du découpage de 2025 issues de la province", "COD-AB"),
    "abandon_suivant_province_origine": ("identifiant", "Valeur de l'ancienne province d'origine (abandon de t à t+1 (cible)) : sert au recalage des provinces scindées", "DGESS, annuaires du primaire"),
    "abandon_brut_suivant_province_origine": ("identifiant", "Valeur de l'ancienne province d'origine (abandon brut de t à t+1) : sert au recalage des provinces scindées", "DGESS, annuaires du primaire"),
    "abandon_precedent_province_origine": ("identifiant", "Valeur de l'ancienne province d'origine (abandon de t-1 à t) : sert au recalage des provinces scindées", "DGESS, annuaires du primaire"),
    "redoublement_precedent_province_origine": ("identifiant", "Valeur de l'ancienne province d'origine (redoublement de t-1 à t) : sert au recalage des provinces scindées", "DGESS, annuaires du primaire"),
    "promotion_precedente_province_origine": ("identifiant", "Valeur de l'ancienne province d'origine (promotion de t-1 à t) : sert au recalage des provinces scindées", "DGESS, annuaires du primaire"),
    "cible_observee": ("identifiant", "Vrai si la cible est observée pour la province de 2025 (faux pour les provinces scindées et l'année à prévoir)", "Calcul Sentinelle"),
    "province_pcode": ("identifiant", "Code de la province de 2025 (47 provinces)", "COD-AB (découpage de juillet 2025)"),
    "province_nom": ("identifiant", "Nom de la province de 2025", "COD-AB (découpage de juillet 2025)"),
    "region_pcode": ("identifiant", "Code de la région de 2025 (17 régions) ; BF pour le pays", "COD-AB (découpage de juillet 2025)"),
    "region_nom": ("identifiant", "Nom de la région de 2025", "COD-AB (découpage de juillet 2025)"),
    "methode_passage": ("identifiant", "Méthode de passage de l'ancien découpage à celui de 2025 pour la ligne",
                        "Calcul Sentinelle d'après le COD-AB, le RGPH 2019 et le CONASUR"),
    "annee_scolaire": ("identifiant", "Année scolaire t", "DGESS, annuaires du primaire"),
    "abandon_brut_suivant": ("cible (brute)", "Abandon apparent du cycle CP1-CM1 entre t et t+1, en %", "DGESS, tableau VIII.3"),
    "abandon_suivant": ("cible", "Abandon entre t et t+1, en % ; vide en cas de rupture de scolarisation ou pour la dernière année", "DGESS, tableau VIII.3"),
    "statut_cible": ("cible", "abandon observé, rupture de scolarisation ou à prévoir", "calculs des auteurs"),
    "rupture_cible": ("cible", f"Vrai si les effectifs varient de plus de {SEUIL_RUPTURE:.0%} entre t et t+1", "DGESS, tableau VIII.3"),
    "evolution_effectifs_suivante": ("cible (contexte)", "Évolution des effectifs entre t et t+1 ; sert à repérer les ruptures, jamais comme variable explicative", "DGESS, tableau VIII.3"),
    "effectif_suivant": ("cible (contexte)", "Effectif total en t+1 ; jamais comme variable explicative", "DGESS, tableau VIII.3"),
    "abandon_precedent": ("explicative", "Abandon entre t-1 et t, en %", "DGESS, tableau VIII.3"),
    "redoublement_precedent": ("explicative", "Redoublement entre t-1 et t, en %", "DGESS, tableau VIII.3"),
    "promotion_precedente": ("explicative", "Promotion entre t-1 et t, en %", "DGESS, tableau VIII.3"),
    "effectif": ("explicative", "Effectif total du primaire en t", "DGESS, tableau VIII.3"),
    "effectif_precedent": ("explicative", "Effectif total en t-1", "DGESS, tableau VIII.3"),
    "evolution_effectifs": ("explicative", "Évolution des effectifs entre t-1 et t", "DGESS, tableau VIII.3"),
    "choc_effectifs": ("explicative", f"Vrai si les effectifs ont varié de plus de {SEUIL_RUPTURE:.0%} entre t-1 et t", "DGESS, tableau VIII.3"),
    "part_filles": ("explicative", "Part des filles dans l'effectif ; vide quand la répartition publiée est invraisemblable", "DGESS, tableau VIII.3"),
    "part_cp1": ("explicative", "Part du CP1 dans l'effectif", "DGESS, tableau VIII.3"),
    "rapport_cm2_cp1": ("explicative", "Effectif du CM2 rapporté à celui du CP1", "DGESS, tableau VIII.3"),
    "eleves_par_maitre": ("explicative", "Élèves par maître chargé de cours, public et privé", "DGESS, tableau I.1"),
    "eleves_par_salle": ("explicative", "Élèves par salle de classe, public et privé", "DGESS, tableau I.1"),
    "part_eleves_prive": ("explicative", "Part des élèves scolarisés dans le privé", "DGESS, tableau I.1"),
    "deplaces": ("explicative", "Déplacés internes accueillis dans la province, dernière situation connue au 31 décembre de l'année de rentrée", "SP/CONASUR"),
    "date_deplaces": ("qualité", "Date de la situation des déplacés retenue", "SP/CONASUR"),
    "deplaces_pour_100_eleves": ("explicative", "Déplacés accueillis pour 100 élèves inscrits", "SP/CONASUR ; DGESS"),
    "ecoles_fermees_province": ("explicative", "Écoles primaires fermées, moyenne des rapports fiables de l'année scolaire", "ST-ESU"),
    "eleves_touches_province": ("explicative", "Élèves des écoles primaires fermées, moyenne des rapports fiables de l'année", "ST-ESU"),
    "ecoles_fermees_region": ("explicative", "Établissements fermés dans la région (tous ordres), moyenne des rapports de l'année", "ST-ESU"),
    "eleves_affectes_region": ("explicative", "Élèves affectés par les fermetures dans la région, moyenne des rapports de l'année", "ST-ESU"),
    "tba_region": ("explicative", "Taux brut d'admission au CP1 de la région en t, en %", "DGESS, base principale, feuille 6"),
    "tbs_region": ("explicative", "Taux brut de scolarisation au primaire de la région en t, en %", "DGESS, base principale, feuille 7"),
    "taux_achevement_region": ("explicative", "Taux d'achèvement du primaire de la région en t, en %", "DGESS, base principale, feuille 8"),
    "ips_tbs_region": ("explicative", "Indice de parité filles / garçons du TBS de la région en t", "DGESS, base principale, feuille 11"),
    "ips_tap_region": ("explicative", "Indice de parité filles / garçons du taux d'achèvement de la région en t", "DGESS, base principale, feuille 12"),
    "tbs_prescolaire_region": ("explicative", "Taux brut de scolarisation au préscolaire de la région en t, en %", "DGESS, base principale, feuille PRESCOLAIRE, tableau 5"),
    "part_ecoles_privees_region": ("explicative", "Part des écoles primaires privées de la région en t", "DGESS, base principale, feuille 13"),
    "adolescents_non_formelle": ("explicative", "Adolescents inscrits dans l'éducation non formelle de la province (campagne achevée à la rentrée de t)", "DGESS, annuaires de l'éducation non formelle, tableau 1.3"),
    "centres_non_formelle_adolescents": ("explicative", "Centres d'éducation non formelle des adolescents de la province (campagne achevée à la rentrée de t)", "DGESS, annuaires de l'éducation non formelle, tableau 1.1"),
    "adolescents_non_formelle_pour_1000_eleves": ("explicative", "Adolescents de l'éducation non formelle pour 1 000 élèves du primaire", "DGESS ; calculs des auteurs"),
    "taux_prescolarisation_province": ("explicative", "Taux de préscolarisation de la province en t, en %", "DGESS, annuaires du préscolaire, tableau 02"),
    "grande_section_province": ("explicative", "Enfants en grande section dans la province en t (futurs entrants au CP1)", "DGESS, annuaires du préscolaire, tableau 9"),
    "pauvrete_province": ("explicative", "Incidence de la pauvreté dans la province (RGPH 2019, constant dans le temps)", "INSD, RGPH 2019, volume 3 (pauvreté)"),
    "profondeur_pauvrete_province": ("explicative", "Profondeur de la pauvreté dans la province (RGPH 2019, constant dans le temps)", "INSD, RGPH 2019, volume 3 (pauvreté)"),
    "travail_enfants_7_14_province": ("explicative", "Enfants de 7 à 14 ans occupés (RGPH 2019, constant dans le temps)", "INSD, RGPH 2019, volume 3 (pauvreté)"),
    "hors_ecole_6_11_province": ("explicative", "Enfants de 6 à 11 ans hors de l'école (RGPH 2019, constant dans le temps)", "INSD, RGPH 2019, volume 3 (pauvreté)"),
    "hors_ecole_12_15_province": ("explicative", "Enfants de 12 à 15 ans hors de l'école (RGPH 2019, constant dans le temps)", "INSD, RGPH 2019, volume 3 (pauvreté)"),
    "filles_17_ans_mariees_province": ("explicative", "Filles de 17 ans mariées (RGPH 2019, constant dans le temps)", "INSD, RGPH 2019, volume 3 (pauvreté)"),
    "alphabetisation_adultes_province": ("explicative", "Alphabétisation des 15-64 ans (RGPH 2019, constant dans le temps)", "INSD, RGPH 2019, volume 3 (pauvreté)"),
    "acte_naissance_province": ("explicative", "Personnes disposant d'un acte de naissance (RGPH 2019, constant dans le temps)", "INSD, RGPH 2019, volume 3 (pauvreté)"),
    "parite_scolarisation_province": ("explicative", "Rapport filles / garçons scolarisés au primaire (RGPH 2019, constant dans le temps)", "INSD, RGPH 2019, volume 3 (pauvreté)"),
    "electricite_province": ("explicative", "Ménages accédant à l'électricité (RGPH 2019, constant dans le temps)", "INSD, RGPH 2019, volume 3 (pauvreté)"),
    "telephone_province": ("explicative", "Ménages accédant à un téléphone (RGPH 2019, constant dans le temps)", "INSD, RGPH 2019, volume 3 (pauvreté)"),
    "part_ecoles_cantine": ("explicative", "Part des écoles disposant d'une cantine scolaire", "DGESS, annuaires du primaire, équipement des écoles"),
    "part_ecoles_latrines": ("explicative", "Part des écoles disposant de latrines", "DGESS, annuaires du primaire, équipement des écoles"),
    "part_ecoles_eau_potable": ("explicative", "Part des écoles disposant d'un point d'eau potable", "DGESS, annuaires du primaire, équipement des écoles"),
    "part_ecoles_electricite": ("explicative", "Part des écoles disposant de l'électricité", "DGESS, annuaires du primaire, équipement des écoles"),
    "part_eleves_plus_3km": ("explicative", "Part des élèves effectuant un trajet de plus de 3 km pour aller à l'école", "DGESS, annuaires du primaire, distance parcourue"),
    "part_ecoles_cycle_incomplet": ("explicative", "Part des écoles de moins de six salles fonctionnelles (cycle incomplet probable)", "DGESS, annuaires du primaire, taille des écoles"),
    "logements_pour_100_maitres": ("explicative", "Logements de maîtres disponibles pour 100 maîtres chargés de cours", "DGESS, annuaires du primaire, logements de maîtres"),
    "manuels_lecture_par_eleve": ("explicative", "Manuels de lecture disponibles par élève", "DGESS, annuaires du primaire, manuels des élèves"),
    "manuels_calcul_par_eleve": ("explicative", "Manuels de calcul disponibles par élève", "DGESS, annuaires du primaire, manuels des élèves"),
    "deficit_places_pour_100_eleves": ("explicative", "Places assises manquantes pour 100 élèves", "DGESS, annuaires du primaire, mobilier des élèves"),
    "part_parents_agriculteurs": ("explicative", "Part des élèves dont les parents sont cultivateurs ou éleveurs", "DGESS, annuaires du primaire, profession des parents"),
    "part_salles_murs_precaires": ("explicative", "Part des salles aux murs semi-durs, en paille ou en banco", "DGESS, annuaires du primaire, nature et état des murs"),
    "part_salles_toit_precaire": ("explicative", "Part des salles couvertes de banco, de paille ou sans toit", "DGESS, annuaires du primaire, nature et état des toitures"),
    "part_salles_recentes": ("explicative", "Part des salles de classe mises en service après 2015", "DGESS, annuaires du primaire, année de mise en service"),
    "tba_province": ("explicative", "Taux brut d'admission au CP1 de la province", "DGESS, annuaires du primaire, taux brut d'admission"),
    "tbs_province": ("explicative", "Taux brut de scolarisation de la province", "DGESS, annuaires du primaire, taux brut de scolarisation"),
    "tns_province": ("explicative", "Taux net de scolarisation de la province (enfants de 6 à 11 ans scolarisés)", "DGESS, annuaires du primaire, taux net de scolarisation"),
    "ecart_tbs_filles_garcons": ("explicative", "Écart entre le TBS des filles et celui des garçons", "DGESS, annuaires du primaire, taux brut de scolarisation"),
    "achevement_province": ("explicative", "Taux d'achèvement du primaire de la province", "DGESS, annuaires du primaire, taux d'achèvement"),
    "reussite_cep_precedente_province": ("explicative", "Taux d'admission au CEP de la province à la session qui clôt t-1", "DGESS, annuaires du primaire, résultats au CEP"),
    "consommation_par_personne_province": ("explicative", "Consommation annuelle moyenne par personne dans la province (2019, constante dans le temps)", "INSD, profils régionaux de pauvreté (2023), mesure EHCVM 2018 et RGPH 2019"),
    "gini_province": ("explicative", "Indice de Gini de la consommation dans la province (2019, constant dans le temps)", "INSD, profils régionaux de pauvreté (2023), mesure EHCVM 2018 et RGPH 2019"),
    "rapport_q90_q10_province": ("explicative", "Rapport entre le 9e et le 1er décile de consommation dans la province (2019)", "INSD, profils régionaux de pauvreté (2023), mesure EHCVM 2018 et RGPH 2019"),
    "part_eleves_12_ans_et_plus": ("explicative", "Part des élèves du primaire âgés de 12 ans ou plus (retard scolaire)", "DGESS, annuaires du primaire, élèves par âge"),
    "part_entrants_cp1_8_ans_et_plus": ("explicative", "Part des nouveaux entrants au CP1 âgés de 8 ans ou plus (entrée tardive)", "DGESS, annuaires du primaire, nouveaux entrants par âge"),
    "part_enseignantes": ("explicative", "Part des femmes parmi les enseignants", "DGESS, annuaires du primaire, enseignants par sexe, âge et expérience"),
    "part_enseignants_debutants": ("explicative", "Part des enseignants ayant de 1 à 5 ans d'expérience", "DGESS, annuaires du primaire, enseignants par sexe, âge et expérience"),
    "abandons_orpaillage_pour_1000_region": ("explicative", "Abandons déclarés pour orpaillage dans la région en t-1, pour 1 000 élèves du primaire", "DGESS, tableaux de bord du primaire"),
    "abandons_mariage_grossesse_pour_1000_region": ("explicative", "Abandons déclarés pour mariage ou grossesse dans la région en t-1, pour 1 000 élèves du primaire", "DGESS, tableaux de bord du primaire"),
    "tba_6e_province": ("explicative", "Taux brut d'admission en 6e de la province, année t", "DGESS, annuaires du post-primaire et du secondaire 2018-2019 à 2022-2023, section II.3.1"),
    "tbs_post_primaire_province": ("explicative", "Taux brut de scolarisation au post-primaire de la province, année t", "DGESS, annuaires du post-primaire et du secondaire 2018-2019 à 2022-2023, section II.3.4"),
    "achevement_post_primaire_province": ("explicative", "Taux d'achèvement du post-primaire de la province, année t", "DGESS, annuaires du post-primaire et du secondaire 2018-2019 à 2022-2023, section II.3.9"),
    "parite_tbs_post_primaire_province": ("explicative", "Indice de parité filles / garçons du TBS du post-primaire, année t", "DGESS, annuaires du post-primaire et du secondaire 2018-2019 à 2022-2023, section II.3.4"),
    "abandon_post_primaire_province": ("explicative", "Abandon moyen en 6e, 5e et 4e (passage de t-1 à t), enseignement général", "DGESS, annuaires du post-primaire et du secondaire 2018-2019 à 2022-2023, section II.3.11"),
    "redoublement_3e_province": ("explicative", "Redoublement en 3e (passage de t-1 à t), enseignement général", "DGESS, annuaires du post-primaire et du secondaire 2018-2019 à 2022-2023, section II.3.11"),
    "ratio_eleves_classe_post_primaire_region": ("explicative", "Élèves par classe au post-primaire public de la région, année t", "DGESS, annuaires du post-primaire et du secondaire 2018-2019 à 2022-2023, section III.1.11"),
    "part_etab_secondaires_publics_electricite_region": ("explicative", "Part des établissements publics du post-primaire et du secondaire disposant de l'électricité (région)", "DGESS, annuaires du post-primaire et du secondaire 2018-2019 à 2022-2023, section III.5.1"),
    "part_etab_secondaires_publics_cantine_region": ("explicative", "Part des établissements publics du post-primaire et du secondaire disposant d'une cantine (région)", "DGESS, annuaires du post-primaire et du secondaire 2018-2019 à 2022-2023, section III.5.1"),
    "ecart_achevement_entree_6e": ("explicative", "Achèvement du primaire moins entrée en 6e (points) : élèves perdus au passage vers le post-primaire", "DGESS, annuaires du primaire et du post-primaire"),
    "reussite_cep_precedente_region": ("explicative", "Taux de réussite au CEP de la région à la session qui clôt t-1 (celle de t n'est pas connue à la rentrée), en %", "DGESS, base principale, feuille 9"),
}

_CLASSES = ["CP1", "CP2", "CE1", "CE2", "CM1", "CM2"]

# Description des variables des tables régionale et nationale tirées de la base principale.
VARIABLES_REGION = {
    "region_ancienne_pcode": "Code de la région (ancien découpage) ; BF pour le pays",
    "region_ancienne_nom": "Nom de la région",
    "annee_scolaire": "Année scolaire",
    "effectif_primaire": "Élèves du primaire",
    "effectif_primaire_filles": "Élèves du primaire, filles",
    "nouveaux_inscrits_cp1": "Nouveaux inscrits au CP1",
    "nouveaux_inscrits_cp1_filles": "Nouveaux inscrits au CP1, filles",
    "tba": "Taux brut d'admission, en %",
    "tba_filles": "Taux brut d'admission des filles, en %",
    "tba_garcons": "Taux brut d'admission des garçons, en %",
    "tbs": "Taux brut de scolarisation, en %",
    "tbs_filles": "Taux brut de scolarisation des filles, en %",
    "tbs_garcons": "Taux brut de scolarisation des garçons, en %",
    "taux_achevement": "Taux d'achèvement du primaire, en %",
    "taux_achevement_filles": "Taux d'achèvement des filles, en %",
    "taux_achevement_garcons": "Taux d'achèvement des garçons, en %",
    "reussite_cep": "Taux de réussite au CEP (session qui clôt l'année), en %",
    "reussite_cep_filles": "Taux de réussite des filles au CEP, en %",
    "reussite_cep_garcons": "Taux de réussite des garçons au CEP, en %",
    "ips_tba": "Indice de parité filles / garçons du TBA",
    "ips_tbs": "Indice de parité filles / garçons du TBS",
    "ips_tap": "Indice de parité filles / garçons du taux d'achèvement",
    "ecoles_primaires": "Écoles primaires",
    "ecoles_primaires_publiques": "Écoles primaires publiques",
    "ecoles_primaires_privees": "Écoles primaires privées",
    "effectif_prescolaire": "Enfants inscrits au préscolaire",
    "tbs_prescolaire": "Taux brut de scolarisation au préscolaire, en %",
    "ips_tbs_prescolaire": "Indice de parité du TBS au préscolaire",
    "structures_prescolaire": "Structures du préscolaire",
    "structures_prescolaire_publiques": "Structures publiques du préscolaire",
    "salles_prescolaire": "Salles du préscolaire",
    "part_filles_primaire": "Part des filles parmi les élèves du primaire",
    "part_ecoles_privees": "Part des écoles primaires privées",
    "eleves_par_ecole": "Élèves du primaire par école",
    "prescolaire_pour_100_nouveaux_cp1": "Enfants du préscolaire pour 100 nouveaux inscrits au CP1",
    "effectif_primaire_public": "Élèves du primaire public",
    "effectif_primaire_prive": "Élèves du primaire privé",
    "effectif_primaire_urbain": "Élèves du primaire en milieu urbain",
    "effectif_primaire_rural": "Élèves du primaire en milieu rural",
    **{f"effectif_{c.lower()}": f"Élèves du {c}, public et privé" for c in _CLASSES},
    **{f"effectif_{c.lower()}_public": f"Élèves du {c} dans le public" for c in _CLASSES},
    "effectif_prescolaire_public": "Enfants du préscolaire public",
    "effectif_prescolaire_prive": "Enfants du préscolaire privé",
    "effectif_prescolaire_communautaire": "Enfants du préscolaire communautaire",
    "effectif_prescolaire_urbain": "Enfants du préscolaire en milieu urbain",
    "effectif_prescolaire_rural": "Enfants du préscolaire en milieu rural",
    "effectif_petite_section": "Enfants en petite section",
    "effectif_moyenne_section": "Enfants en moyenne section",
    "effectif_grande_section": "Enfants en grande section",
    "part_prive_primaire": "Part des élèves du primaire dans le privé",
    "part_urbain_primaire": "Part des élèves du primaire en milieu urbain",
    "rapport_cm2_cp1_national": "Élèves du CM2 rapportés à ceux du CP1",
}

# Noms publiés : chaque variable scolaire nomme son ordre d'enseignement (module nommage).
# Démographie : mêmes descriptions dans les panels régionaux que dans le panel provincial.
VARIABLES_REGION.update({nom: VARIABLES[nom][1] for nom in (
    "population_totale", "moins_15", "age_15_64", "plus_64", "enfants_3_5", "enfants_5", "enfants_6_11",
    "enfants_6_11_filles", "enfants_6_11_garcons", "enfants_12_15", "enfants_12_15_filles", "enfants_12_15_garcons",
    "jeunes_16_18", "methode_population", "rapport_dependance", "part_moins_15", "croissance_enfants_6_11")})
# Indicateurs du RGPH 2019 à chaque niveau (module recensement).
for _niveau in ("province", "region", "commune"):
    for _nom, (_libelle, _unite, _calcul, _limites) in recensement.descriptions(_niveau).items():
        FICHES.setdefault(_nom, (_libelle, _unite, _calcul, _limites))
        VARIABLES.setdefault(_nom, ("explicative", _libelle, recensement.SOURCE))
        VARIABLES_REGION.setdefault(_nom, _libelle)

# Indicateurs des tableaux de bord du post-primaire et du secondaire : régions et pays seulement.
_SOURCE_TDB = "DGESS, tableaux de bord du post-primaire et du secondaire 2023 à 2025"
_LIMITES_TDB = ("Valeur publiée pour la région ou le pays, jamais répartie d'un total national ; les régions "
                "scindées en 2025 n'ont pas d'effectif (aucune ventilation communale contemporaine)")
for _ordre, _nom_ordre in (("post_primaire", "du post-primaire"), ("secondaire", "du secondaire")):
    for _indicateur, _libelle, _unite in (("effectif", "Élèves", "élèves"), ("tba", "Taux brut d'admission", "%"),
                                          ("tbs", "Taux brut de scolarisation", "%"),
                                          ("taux_achevement", "Taux d'achèvement", "%")):
        for _sexe, _suffixe in (("ensemble", ""), ("filles", "_filles"), ("garçons", "_garcons")):
            _nom = f"{_indicateur}_{_ordre}{_suffixe}"
            _texte = f"{_libelle} {_nom_ordre}" + ("" if _sexe == "ensemble" else f", {_sexe}")
            VARIABLES[_nom] = ("contexte", _texte, _SOURCE_TDB)
            VARIABLES_REGION[_nom] = _texte
            FICHES[_nom] = (_texte, _unite, "valeur publiée", _LIMITES_TDB)

nommage.etendre(FICHES, VARIABLES, VARIABLES_REGION)

# Relations entre tables, pour le schéma de la base (rôle architecte).
RELATIONS = [
    ("panel_province_2025", "province_pcode", "province", "province_pcode", "plusieurs à un"),
    ("panel_province_2025", "province_ancienne_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("panel_region_2025", "region_pcode", "region", "region_pcode", "plusieurs à un"),
    ("panel_province_annee", "province_ancienne_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("panel_province_annee", "region_ancienne_pcode", "region_ancienne", "region_ancienne_pcode", "plusieurs à un"),
    ("panel_mensuel_province", "province_ancienne_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("province", "province_ancienne_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un (2 provinces scindées)"),
    ("commune", "province_ancienne_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("commune", "province_pcode", "province", "province_pcode", "plusieurs à un"),
    ("fait_effectifs_retenus", "entite_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("fait_offre_province", "entite_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("fait_flux_publie", "entite_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("fait_esu_province", "province_ancienne_pcode", "province_ancienne", "province_ancienne_pcode", "plusieurs à un"),
    ("fait_esu_region", "region_ancienne_pcode", "region_ancienne", "region_ancienne_pcode", "plusieurs à un"),
    ("fait_pdi_commune", "commune_pcode", "commune", "commune_pcode", "plusieurs à un"),
    ("fait_base_principale", "entite_pcode", "region_ancienne", "region_ancienne_pcode", "plusieurs à un"),
    ("panel_region_annee", "region_ancienne_pcode", "region_ancienne", "region_ancienne_pcode", "plusieurs à un"),
    ("panel_province_annee", "region_ancienne_pcode, annee_scolaire", "panel_region_annee",
     "region_ancienne_pcode, annee_scolaire", "plusieurs à un"),
    ("serie_nationale_annee", "annee_scolaire", "panel_region_annee", "annee_scolaire (ligne BF)", "un à un"),
]


def dictionnaire(panel: pd.DataFrame) -> pd.DataFrame:
    lignes = []
    for colonne in panel.columns:
        role, description, source = VARIABLES.get(colonne, ("", "", ""))
        renseignees = panel[colonne].notna()
        annees = panel.loc[renseignees, "annee_scolaire"]
        lignes.append({"variable": colonne, "role": role, "description": description, "source": source,
                       "part_manquante": round(1 - renseignees.mean(), 3),
                       "premiere_annee": annees.min() if len(annees) else "",
                       "derniere_annee": annees.max() if len(annees) else ""})
    return pd.DataFrame(lignes)


def dictionnaire_region(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    lignes = []
    for nom, table in tables.items():
        for colonne in table.columns:
            source = "OpenStreetMap (HOT)" if colonne == "region_ancienne_nom" else "DGESS, base principale"
            lignes.append({"table": nom, "variable": colonne, "description": VARIABLES_REGION.get(colonne, ""),
                           "source": source, "part_manquante": round(float(table[colonne].isna().mean()), 3)})
    return pd.DataFrame(lignes)


def controles(panel: pd.DataFrame, mensuel: pd.DataFrame, dico: pd.DataFrame) -> pd.DataFrame:
    cles = ["province_ancienne_pcode", "annee_scolaire"]
    explicatives = dico.loc[dico["role"] == "explicative", "variable"]
    interdites = {"abandon_brut_suivant", "abandon_suivant", "evolution_effectifs_suivante", "effectif_suivant"}
    statuts = panel["statut_cible"].value_counts()
    contours = gpd.read_file(config.BASE_GEOPACKAGE, layer="province", engine="pyogrio")
    resultats = [
        ("une_ligne_par_province_et_annee", not panel.duplicated(cles).any() and len(panel) == 45 * panel["annee_scolaire"].nunique(),
         f"{len(panel)} lignes = 45 provinces × {panel['annee_scolaire'].nunique()} années, sans doublon"),
        ("cible_renseignee", statuts.get("abandon observé", 0) >= 300,
         ", ".join(f"{k} : {v}" for k, v in statuts.items())),
        ("aucune_variable_explicative_venant_du_futur", not (set(explicatives) & interdites),
         "les variables de t+1 servent seulement à définir la cible"),
        ("toutes_les_variables_decrites", (dico["role"] != "").all(),
         f"{len(dico)} variables décrites" if (dico["role"] != "").all()
         else "sans description : " + ", ".join(dico.loc[dico["role"] == "", "variable"])),
        ("jointure_carte_2025", set(panel["province_ancienne_pcode"]) == set(contours["province_ancienne_pcode"]),
         f"les 45 provinces du panel couvrent les {len(contours)} provinces de 2025"),
        ("panel_mensuel_sans_doublon", not mensuel.duplicated(["province_ancienne_pcode", "mois"]).any(),
         f"{len(mensuel)} lignes, {mensuel['mois'].nunique()} mois ({mensuel['mois'].min()} à {mensuel['mois'].max()})"),
    ]
    return pd.DataFrame(resultats, columns=["controle", "conforme", "detail"])


def controles_region(region: pd.DataFrame, nationale: pd.DataFrame, dico_region: pd.DataFrame,
                     panel: pd.DataFrame) -> pd.DataFrame:
    regions = region[region["region_ancienne_pcode"] != "BF"]
    pays = region[region["region_ancienne_pcode"] == "BF"].set_index("annee_scolaire")
    ecart = (regions.groupby("annee_scolaire")["effectif_primaire"].sum() - pays["effectif_primaire"]).abs().max()
    achevement = pays.loc["2024-2025", "taux_achevement"]
    n = nationale.set_index("annee_scolaire")
    statuts = (n["effectif_primaire_public"] + n["effectif_primaire_prive"] - n["effectif_primaire"]).abs().max()
    renseigne = panel["taux_achevement_region"].notna().mean()
    decrites = (dico_region["description"] != "").all()
    resultats = [
        ("panel_region_une_ligne_par_region_et_annee",
         not region.duplicated(["region_ancienne_pcode", "annee_scolaire"]).any() and len(region) == 14 * 10,
         f"{len(region)} lignes = 13 régions et le pays × 10 années"),
        ("population_pays_jointe_2024_2025", pays.loc["2024-2025", "population_totale"] > 0,
         "population du pays jointe à la ligne BF, au même grain que les régions"),
        ("population_regions_egale_pays",
         (regions.groupby("annee_scolaire")["population_totale"].sum(min_count=1)
          - pays["population_totale"]).dropna().abs().le(1).all(),
         "somme des 13 régions = pays ; aucune moyenne de rapports démographiques"),
        ("somme_des_regions_egale_national", ecart <= 0.5, f"écart maximal {ecart:g} élève sur 10 années"),
        ("public_plus_prive_egal_total_national", statuts <= 0.5, f"écart maximal {statuts:g} élève"),
        ("taux_achevement_national_2024_2025", abs(achevement - 51.6) < 0.05,
         f"{achevement:.1f} % en 2024-2025, valeur citée dans la note d'intention"),
        ("contexte_regional_joint_au_panel", renseigne == 1,
         f"taux d'achèvement régional renseigné pour {renseigne:.0%} des lignes du panel"),
        ("variables_regionales_decrites", decrites,
         f"{len(dico_region)} variables décrites" if decrites
         else "sans description : " + ", ".join(dico_region.loc[dico_region["description"] == "", "variable"])),
    ]
    return pd.DataFrame(resultats, columns=["controle", "conforme", "detail"])


def controles_demographie(panel: pd.DataFrame, panel_2025: pd.DataFrame, communes: pd.DataFrame) -> pd.DataFrame:
    a = panel.groupby("annee_scolaire")["enfants_6_11"].sum()
    b = panel_2025.groupby("annee_scolaire")["enfants_6_11"].sum()
    c = communes.groupby("annee_scolaire")["enfants_6_11"].sum()
    ecart = max((a - b).abs().max(), (a - c).abs().max())
    validation = demographie.valider()
    renseigne = panel["enfants_6_11"].notna().mean()
    tbs = communes["tbs_primaire_commune"].notna()
    resultats = [
        ("demographie_communes_provinces_identiques", bool(ecart <= 1),
         f"enfants de 6 à 11 ans : 351 communes = 45 anciennes provinces = 47 provinces de 2025, chaque année "
         f"(écart maximal {ecart:.0f})"),
        ("demographie_retroprojection_validee", bool(all(0.80 <= v <= 1.05 for v in validation.values())),
         "6-11 ans rétroprojetés au niveau national, rapportés aux anciennes projections (base RGPH 2006) : "
         + ", ".join(f"{k} {v:.3f}" for k, v in sorted(validation.items()))
         + " ; écart attendu, les anciennes projections surestimaient la population recensée en 2019"),
        ("demographie_panel_renseigne", bool(renseigne == 1),
         f"population de 6 à 11 ans renseignée pour {renseigne:.0%} des lignes du panel (2016-2017 à 2024-2025)"),
        ("panel_communal_351_communes", communes["commune_pcode"].nunique() == 351
         and not communes.duplicated(["commune_pcode", "annee_scolaire"]).any(),
         f"{communes['commune_pcode'].nunique()} communes × {communes['annee_scolaire'].nunique()} années ; TBS "
         f"communal du primaire calculable pour {int(tbs.sum())} lignes"),
    ]
    return pd.DataFrame(resultats, columns=["controle", "conforme", "detail"])


def executer_transformation() -> dict[str, pd.DataFrame]:
    sortie = config.verifier_ecriture(SORTIE)
    sortie.mkdir(parents=True, exist_ok=True)
    # Population annuelle par âge (projections actualisées de l'INSD, rétroprojetées avant 2020).
    panel = demographie.ajouter(construire_panel(), "province_ancienne_pcode")
    mensuel = construire_panel_mensuel()
    region = demographie.ajouter(construire_panel_region(), "region_ancienne_pcode")
    region = recensement.ajouter(region, recensement.region_ancienne(), "region_ancienne_pcode")
    communes = demographie.panel_communes()
    nationale = construire_serie_nationale()
    dico = dictionnaire(panel)
    dico_region = dictionnaire_region({"panel_region_annee": region, "serie_nationale_annee": nationale})
    relations = pd.DataFrame(RELATIONS, columns=["table", "cle", "table_liee", "cle_liee", "cardinalite"])
    # Mêmes panels dans le découpage de 2025, pour la restitution (le modèle reste entraîné sur 45 provinces).
    panel_2025 = decoupage_2025.panel_province_2025(panel)
    region_2025 = decoupage_2025.panel_region_2025(region, panel_2025)
    panel_2025 = decoupage_2025.contexte_regional_2025(panel_2025, region_2025)
    # Unités de 2025 : population exacte (somme de leurs communes), jamais héritée ni répartie.
    colonnes_demo = [c for c in demographie.demographie("province_pcode").columns
                     if c not in ("province_pcode", "annee_scolaire")]
    panel_2025 = demographie.ajouter(panel_2025.drop(columns=[c for c in colonnes_demo if c in panel_2025]),
                                     "province_pcode")
    region_2025 = demographie.ajouter(region_2025.drop(columns=[c for c in colonnes_demo if c in region_2025]),
                                      "region_pcode")
    # RGPH 2019 des régions de 2025 : publié si la région est inchangée, sinon recalculé sur ses communes.
    region_2025 = recensement.ajouter(region_2025, recensement.region_2025(decoupage_2025._communes()), "region_pcode")
    internes = {"panel_province_annee": panel, "panel_mensuel_province": mensuel, "panel_region_annee": region,
                "serie_nationale_annee": nationale, "panel_province_2025": panel_2025, "panel_region_2025": region_2025,
                "panel_commune_annee": communes}
    bases = nommage.publier(internes)
    metadonnees = metadonnees_modele.ecrire(bases, VARIABLES, VARIABLES_REGION, sortie / "metadonnees")
    conforme, detail = metadonnees["controle"]
    verifications = pd.concat([controles(panel, mensuel, dico),
                               controles_region(region, nationale, dico_region, panel),
                               decoupage_2025.controles(panel, panel_2025, region, region_2025),
                               controles_demographie(panel, panel_2025, communes),
                               pd.DataFrame([{"controle": "recensement_2019_tous_niveaux",
                                              "conforme": recensement.controle(panel, panel_2025, communes)[0],
                                              "detail": recensement.controle(panel, panel_2025, communes)[1]}]),
                               pd.DataFrame([{"controle": "fiches_completes", "conforme": conforme, "detail": detail}])],
                              ignore_index=True)
    resultat = {**bases, "dictionnaire_variables_modele": dictionnaire(bases["panel_province_annee"]),
                "dictionnaire_variables_region": dictionnaire_region(
                    {n: bases[n] for n in ("panel_region_annee", "serie_nationale_annee")}),
                "schema_relations": relations,
                "controles_transformation": verifications}
    for nom, table in resultat.items():
        table.to_csv(sortie / f"{nom}.csv", sep=config.SEPARATEUR, encoding=config.ENCODAGE_SORTIE, index=False)
    # Base finale du découpage de 2025 : un onglet par panel et par ordre d'enseignement.
    nommage.classeur_base_finale({n: bases[n] for n in ("panel_province_2025", "panel_region_2025",
                                                         "panel_commune_annee")},
                                 metadonnees["dictionnaire"], sortie / "sentinelle_base_finale_decoupage_2025.xlsx")
    return resultat
