"""Fiches des variables et des tables des bases du modèle (étape 03).

Le dictionnaire complet d'une variable réunit deux parties :

- ce qui est rédigé ici une fois pour toutes : libellé, unité, mode de calcul,
  limites connues (et, dans ``VARIABLES`` / ``VARIABLES_REGION``, le rôle, la
  description et la source) ;
- ce qui est mesuré sur la table à chaque exécution : type, plage observée ou
  valeurs possibles, part de valeurs manquantes, années couvertes.

Une variable sans libellé ou sans unité est signalée par le contrôle
``fiches_completes``.
"""

from __future__ import annotations

PUBLIE = "valeur publiée"
SANS = "sans unité"

# variable : (libellé, unité, mode de calcul, limites connues)
FICHES: dict[str, tuple[str, str, str, str]] = {
    # Identifiants.
    "province_ancienne_pcode": ("Code de la province", SANS, "P-code COD-AB de l'ancien découpage (45 provinces)", ""),
    "province_ancienne_nom": ("Province", SANS, "", ""),
    "region_ancienne_pcode": ("Code de la région", SANS, "P-code COD-AB de l'ancien découpage ; BF pour le pays", ""),
    "region_ancienne_nom": ("Région", SANS, "", ""),
    "provinces_actuelles": ("Provinces de 2025", SANS, "P-codes des provinces du découpage de juillet 2025 issues de l'ancienne province",
                            "Soum et Tapoa scindées en deux provinces : elles reçoivent la valeur de l'ancienne province"),
    "annee_scolaire": ("Année scolaire", SANS, "", ""),
    "mois": ("Mois", SANS, "AAAA-MM de la situation retenue", ""),
    "date_situation": ("Date de la situation", SANS, "", ""),
    # Cible.
    "abandon_brut_suivant": ("Abandon de t à t+1 (brut)", "%",
                             "Cohorte reconstituée, CP1 à CM1 : [E(g,t) - (E(g+1,t+1) - R(g+1,t+1)) - R(g,t+1)] / E(g,t), "
                             "sommé sur les classes avant division",
                             "Mesure toutes les pertes nettes d'élèves, y compris les départs vers une autre province"),
    "abandon_suivant": ("Abandon de t à t+1", "%", "abandon_brut_suivant, vidé en cas de rupture de scolarisation",
                        "Vide pour 2024-2025 (à prévoir) et pour les 39 ruptures"),
    "statut_cible": ("Statut de la cible", SANS, "abandon observé, rupture de scolarisation (|évolution| > 30 %) ou à prévoir", ""),
    "rupture_cible": ("Rupture de scolarisation", "booléen", "|evolution_effectifs_suivante| > 0,30", ""),
    "evolution_effectifs_suivante": ("Évolution des effectifs de t à t+1", "proportion", "effectif_suivant / effectif - 1",
                                     "Sert à définir la cible ; interdite comme variable explicative"),
    "effectif_suivant": ("Effectif en t+1", "élèves", "effectif de l'année suivante", "Interdite comme variable explicative"),
    # Passé scolaire et effectifs.
    "abandon_precedent": ("Abandon de t-1 à t", "%", "Cohorte reconstituée, passage précédent", ""),
    "redoublement_precedent": ("Redoublement de t-1 à t", "%", "R(g,t) / E(g,t-1), sommé sur CP1 à CM1", ""),
    "promotion_precedente": ("Promotion de t-1 à t", "%", "(E(g+1,t) - R(g+1,t)) / E(g,t-1), sommé sur CP1 à CM1", ""),
    "effectif": ("Élèves du primaire", "élèves", PUBLIE, ""),
    "effectif_precedent": ("Élèves en t-1", "élèves", PUBLIE, ""),
    "evolution_effectifs": ("Évolution des effectifs de t-1 à t", "proportion", "effectif / effectif_precedent - 1", ""),
    "choc_effectifs": ("Choc d'effectifs", "booléen", "|evolution_effectifs| > 0,30", ""),
    "part_filles": ("Part des filles", "proportion", "filles / total",
                    "Vide en 2024-2025 pour 31 provinces : répartition par sexe de l'annuaire invraisemblable"),
    "part_cp1": ("Part du CP1", "proportion", "effectif CP1 / effectif total", ""),
    "rapport_cm2_cp1": ("Rapport CM2 / CP1", "rapport", "effectif CM2 / effectif CP1", ""),
    # Offre.
    "eleves_par_maitre": ("Élèves par maître", "élèves par maître", "élèves / maîtres chargés de cours (public et privé)", ""),
    "eleves_par_salle": ("Élèves par salle", "élèves par salle", "élèves / salles de classe (public et privé)", ""),
    "part_eleves_prive": ("Part des élèves du privé", "proportion", "élèves du privé / élèves", ""),
    # Crise.
    "deplaces": ("Déplacés internes accueillis", "personnes", "somme des communes de la province",
                 "Situations disponibles de janvier 2019 à mars 2023"),
    "enfants_deplaces": ("Enfants déplacés", "personnes", "somme des communes", "Non recensés séparément avant septembre 2021"),
    "date_deplaces": ("Date de la situation des déplacés", SANS, "dernière situation des 6 mois précédant le 31 décembre de t", ""),
    "deplaces_pour_100_eleves": ("Déplacés pour 100 élèves", "personnes pour 100 élèves", "100 × deplaces / effectif", ""),
    "variation_un_releve": ("Variation sur un relevé", "proportion", "deplaces / deplaces du relevé précédent - 1", ""),
    "variation_trois_releves": ("Variation sur trois relevés", "proportion", "deplaces / deplaces trois relevés plus tôt - 1", ""),
    "ecoles_fermees_province": ("Écoles fermées (province)", "écoles", "moyenne des rapports ESU fiables de l'année",
                                "Rapports fiables seulement de novembre 2021 à mai 2022 et en octobre 2023"),
    "eleves_touches_province": ("Élèves des écoles fermées (province)", "élèves", "moyenne des rapports ESU fiables de l'année", ""),
    "ecoles_fermees_region": ("Établissements fermés (région)", "établissements", "moyenne des rapports de l'année (tous ordres)",
                              "Tous ordres d'enseignement confondus"),
    "eleves_affectes_region": ("Élèves affectés (région)", "élèves", "moyenne des rapports de l'année", ""),
    # Contexte régional, base principale.
    "tba_region": ("TBA de la région", "%", PUBLIE, ""),
    "tbs_region": ("TBS de la région", "%", PUBLIE, ""),
    "taux_achevement_region": ("Taux d'achèvement de la région", "%", PUBLIE, ""),
    "ips_tbs_region": ("Parité du TBS (région)", "indice", PUBLIE, "Rapport filles / garçons ; 1 = parité"),
    "ips_tap_region": ("Parité de l'achèvement (région)", "indice", PUBLIE, "Rapport filles / garçons ; 1 = parité"),
    "tbs_prescolaire_region": ("TBS du préscolaire (région)", "%", PUBLIE, ""),
    "part_ecoles_privees_region": ("Part des écoles privées (région)", "proportion", "écoles privées / écoles", ""),
    "reussite_cep_precedente_region": ("Réussite au CEP, session précédente (région)", "%",
                                       "taux de la session qui clôt t-1", "Décalé d'un an : la session de t n'est pas connue à la rentrée"),
    # Éducation non formelle et préscolaire.
    "adolescents_non_formelle": ("Adolescents en éducation non formelle", "apprenants", "campagne Y rattachée à l'année Y-(Y+1)",
                                 "Campagnes 2018, 2019, 2020 et 2024 seulement"),
    "centres_non_formelle_adolescents": ("Centres pour adolescents", "centres", "campagne Y rattachée à l'année Y-(Y+1)",
                                         "Campagnes 2018, 2019, 2020 et 2024 seulement"),
    "adolescents_non_formelle_pour_1000_eleves": ("Adolescents en éducation non formelle pour 1 000 élèves",
                                                  "apprenants pour 1 000 élèves", "1000 × adolescents_non_formelle / effectif", ""),
    "taux_prescolarisation_province": ("Taux de préscolarisation (province)", "%", PUBLIE, "2023-2024 et 2024-2025 seulement"),
    "grande_section_province": ("Grande section (province)", "enfants", PUBLIE, "2023-2024 et 2024-2025 seulement"),
    # Conditions de scolarisation (annuaires DGESS, province, année t).
    "part_ecoles_cantine": ("Écoles avec cantine", "proportion", "écoles disposant d'une cantine / écoles (public et privé)", ""),
    "part_ecoles_latrines": ("Écoles avec latrines", "proportion", "écoles disposant de latrines / écoles", ""),
    "part_ecoles_eau_potable": ("Écoles avec eau potable", "proportion", "écoles disposant d'eau potable / écoles", ""),
    "part_ecoles_electricite": ("Écoles avec électricité", "proportion", "écoles disposant de l'électricité / écoles", ""),
    "part_eleves_plus_3km": ("Élèves à plus de 3 km", "%", "part des élèves à 3-5 km + part à plus de 5 km", ""),
    "part_ecoles_cycle_incomplet": ("Écoles de moins de six salles", "proportion", "écoles ayant 0 à 5 salles fonctionnelles / écoles", "Une école à six classes peut offrir le cycle complet ; en dessous, classes multigrades ou cycle interrompu"),
    "logements_pour_100_maitres": ("Logements pour 100 maîtres", "logements pour 100 maîtres", "100 × logements de maîtres / maîtres chargés de cours", ""),
    "manuels_lecture_par_eleve": ("Manuels de lecture par élève", "manuels par élève", "manuels de lecture / élèves", ""),
    "manuels_calcul_par_eleve": ("Manuels de calcul par élève", "manuels par élève", "manuels de calcul / élèves", ""),
    "deficit_places_pour_100_eleves": ("Places assises manquantes pour 100 élèves", "places pour 100 élèves", "100 × déficit de places assises / effectif", ""),
    "part_parents_agriculteurs": ("Élèves de parents cultivateurs ou éleveurs", "proportion", "(cultivateurs + éleveurs) / ensemble des professions", "Les intitulés des autres professions ont changé selon les éditions ; seules ces deux colonnes sont stables"),
    "part_salles_murs_precaires": ("Salles aux murs précaires", "proportion", "(murs semi-durs + paille ou banco) / salles", ""),
    "part_salles_toit_precaire": ("Salles au toit précaire", "proportion", "(toit en banco + paille + sans toit) / salles", "Colonne « sans toit » absente avant 2019-2020 (comptée comme nulle)"),
    "part_salles_recentes": ("Salles mises en service après 2015", "proportion", "salles mises en service après 2015 / salles", ""),
    "tba_province": ("TBA de la province", "%", "valeur publiée (garçons et filles)", ""),
    "tbs_province": ("TBS de la province", "%", "valeur publiée (garçons et filles)", "Peut dépasser 100 %"),
    "tns_province": ("TNS de la province", "%", "valeur publiée (garçons et filles)", ""),
    "ecart_tbs_filles_garcons": ("Écart de TBS filles - garçons", "points de %", "TBS des filles - TBS des garçons", ""),
    "achevement_province": ("Taux d'achèvement de la province", "%", "valeur publiée (garçons et filles)", ""),
    "reussite_cep_precedente_province": ("Réussite au CEP, session précédente (province)", "%", "taux d'admission de la session qui clôt t-1", "Décalé d'un an : la session de t n'est pas connue à la rentrée"),
    # Consommation et inégalités (profils régionaux de pauvreté).
    "consommation_par_personne_province": ("Consommation par personne (province)", "FCFA", "valeur publiée", "Mesure de 2019 republiée en 2023 ; pas de profil pour la Boucle du Mouhoun, les Cascades et le Centre-Est (11 provinces sans valeur)"),
    "gini_province": ("Gini de la consommation (province)", "indice", "valeur publiée", "Mesure de 2019 republiée en 2023 ; pas de profil pour la Boucle du Mouhoun, les Cascades et le Centre-Est (11 provinces sans valeur)"),
    "rapport_q90_q10_province": ("Rapport interdécile q90/q10 (province)", "rapport", "valeur publiée", "Mesure de 2019 republiée en 2023 ; pas de profil pour la Boucle du Mouhoun, les Cascades et le Centre-Est (11 provinces sans valeur)"),
    # Répartitions par âge et enseignants (annuaires DGESS, province, année t).
    "part_eleves_12_ans_et_plus": ("Élèves de 12 ans et plus", "proportion", "élèves de 12 ans ou plus / élèves", "L'âge officiel du primaire est 6-11 ans : au-delà, retard scolaire ou entrée tardive"),
    "part_entrants_cp1_8_ans_et_plus": ("Nouveaux entrants au CP1 de 8 ans et plus", "proportion", "nouveaux entrants de 8 ans ou plus / nouveaux entrants", ""),
    "part_enseignantes": ("Part des enseignantes", "proportion", "femmes / enseignants (public et privé)", ""),
    "part_enseignants_debutants": ("Enseignants de 1 à 5 ans d'expérience", "proportion", "enseignants de 1 à 5 ans d'expérience / enseignants", ""),
    # Causes déclarées de l'abandon (tableaux de bord DGESS, région, année t-1).
    "abandons_orpaillage_pour_1000_region": ("Abandons pour orpaillage pour 1 000 élèves (région, t-1)", "élèves pour 1 000",
                                             "1000 × abandons pour orpaillage / élèves du primaire de la région", "Causes de t-1 (publiées dans l'édition de t) ; seulement les abandons dont la cause est déclarée ; vide pour 2016-2017 et 2024-2025"),
    "abandons_mariage_grossesse_pour_1000_region": ("Abandons pour mariage ou grossesse pour 1 000 élèves (région, t-1)",
                                                    "élèves pour 1 000",
                                                    "1000 × (abandons pour mariage + grossesse) / élèves de la région", "Causes de t-1 (publiées dans l'édition de t) ; seulement les abandons dont la cause est déclarée ; vide pour 2016-2017 et 2024-2025"),
    # Conditions de vie (RGPH 2019).
    "pauvrete_province": ("Incidence de la pauvreté dans la province", "%", "valeur publiée pour la province en 2019, répétée chaque année", "Mesure unique de 2019 : explique les écarts entre provinces, pas les évolutions ; ne voit pas la crise après 2019"),
    "profondeur_pauvrete_province": ("Profondeur de la pauvreté dans la province", "%", "valeur publiée pour la province en 2019, répétée chaque année", "Mesure unique de 2019 : explique les écarts entre provinces, pas les évolutions ; ne voit pas la crise après 2019"),
    "travail_enfants_7_14_province": ("Enfants de 7 à 14 ans occupés", "%", "valeur publiée pour la province en 2019, répétée chaque année", "Mesure unique de 2019 : explique les écarts entre provinces, pas les évolutions ; ne voit pas la crise après 2019"),
    "hors_ecole_6_11_province": ("Enfants de 6 à 11 ans hors de l'école", "%", "valeur publiée pour la province en 2019, répétée chaque année", "Mesure unique de 2019 : explique les écarts entre provinces, pas les évolutions ; ne voit pas la crise après 2019"),
    "hors_ecole_12_15_province": ("Enfants de 12 à 15 ans hors de l'école", "%", "valeur publiée pour la province en 2019, répétée chaque année", "Mesure unique de 2019 : explique les écarts entre provinces, pas les évolutions ; ne voit pas la crise après 2019"),
    "filles_17_ans_mariees_province": ("Filles de 17 ans mariées", "%", "valeur publiée pour la province en 2019, répétée chaque année", "Mesure unique de 2019 : explique les écarts entre provinces, pas les évolutions ; ne voit pas la crise après 2019"),
    "alphabetisation_adultes_province": ("Alphabétisation des 15-64 ans", "%", "valeur publiée pour la province en 2019, répétée chaque année", "Mesure unique de 2019 : explique les écarts entre provinces, pas les évolutions ; ne voit pas la crise après 2019"),
    "acte_naissance_province": ("Personnes disposant d'un acte de naissance", "%", "valeur publiée pour la province en 2019, répétée chaque année", "Mesure unique de 2019 : explique les écarts entre provinces, pas les évolutions ; ne voit pas la crise après 2019"),
    "parite_scolarisation_province": ("Rapport filles / garçons scolarisés au primaire", "rapport", "valeur publiée pour la province en 2019, répétée chaque année", "Mesure unique de 2019 : explique les écarts entre provinces, pas les évolutions ; ne voit pas la crise après 2019"),
    "electricite_province": ("Ménages accédant à l'électricité", "%", "valeur publiée pour la province en 2019, répétée chaque année", "Mesure unique de 2019 : explique les écarts entre provinces, pas les évolutions ; ne voit pas la crise après 2019"),
    "telephone_province": ("Ménages accédant à un téléphone", "%", "valeur publiée pour la province en 2019, répétée chaque année", "Mesure unique de 2019 : explique les écarts entre provinces, pas les évolutions ; ne voit pas la crise après 2019"),
    # Tables régionale et nationale.
    "effectif_primaire": ("Élèves du primaire", "élèves", PUBLIE, ""),
    "effectif_primaire_filles": ("Élèves du primaire, filles", "élèves", PUBLIE, ""),
    "nouveaux_inscrits_cp1": ("Nouveaux inscrits au CP1", "élèves", PUBLIE, ""),
    "nouveaux_inscrits_cp1_filles": ("Nouveaux inscrits au CP1, filles", "élèves", PUBLIE, ""),
    "tba": ("TBA", "%", PUBLIE, "Peut dépasser 100 % (élèves hors de l'âge officiel)"),
    "tba_filles": ("TBA des filles", "%", PUBLIE, ""),
    "tba_garcons": ("TBA des garçons", "%", PUBLIE, ""),
    "tbs": ("TBS", "%", PUBLIE, "Peut dépasser 100 % (élèves hors de l'âge officiel)"),
    "tbs_filles": ("TBS des filles", "%", PUBLIE, ""),
    "tbs_garcons": ("TBS des garçons", "%", PUBLIE, ""),
    "taux_achevement": ("Taux d'achèvement", "%", PUBLIE, ""),
    "taux_achevement_filles": ("Taux d'achèvement des filles", "%", PUBLIE, ""),
    "taux_achevement_garcons": ("Taux d'achèvement des garçons", "%", PUBLIE, ""),
    "reussite_cep": ("Réussite au CEP", "%", PUBLIE, "Session de fin d'année"),
    "reussite_cep_filles": ("Réussite des filles au CEP", "%", PUBLIE, ""),
    "reussite_cep_garcons": ("Réussite des garçons au CEP", "%", PUBLIE, ""),
    "ips_tba": ("Parité du TBA", "indice", PUBLIE, "Rapport filles / garçons"),
    "ips_tbs": ("Parité du TBS", "indice", PUBLIE, "Rapport filles / garçons"),
    "ips_tap": ("Parité de l'achèvement", "indice", PUBLIE, "Rapport filles / garçons"),
    "ecoles_primaires": ("Écoles primaires", "écoles", PUBLIE, ""),
    "ecoles_primaires_publiques": ("Écoles primaires publiques", "écoles", PUBLIE, ""),
    "ecoles_primaires_privees": ("Écoles primaires privées", "écoles", PUBLIE, ""),
    "effectif_prescolaire": ("Enfants du préscolaire", "enfants", PUBLIE, "Saut brusque en 2024-2025, signalé"),
    "tbs_prescolaire": ("TBS du préscolaire", "%", PUBLIE, ""),
    "ips_tbs_prescolaire": ("Parité du TBS au préscolaire", "indice", PUBLIE, ""),
    "structures_prescolaire": ("Structures du préscolaire", "structures", PUBLIE,
                               "Statuts privé et communautaire apparemment intervertis en 2019-2020 dans plusieurs régions"),
    "structures_prescolaire_publiques": ("Structures publiques du préscolaire", "structures", PUBLIE, "Saut brusque en 2024-2025"),
    "salles_prescolaire": ("Salles du préscolaire", "salles", PUBLIE, ""),
    "part_filles_primaire": ("Part des filles", "proportion", "effectif_primaire_filles / effectif_primaire", ""),
    "part_ecoles_privees": ("Part des écoles privées", "proportion", "ecoles_primaires_privees / ecoles_primaires", ""),
    "eleves_par_ecole": ("Élèves par école", "élèves par école", "effectif_primaire / ecoles_primaires", ""),
    "prescolaire_pour_100_nouveaux_cp1": ("Préscolaire pour 100 nouveaux inscrits au CP1", "enfants pour 100 élèves",
                                          "100 × effectif_prescolaire / nouveaux_inscrits_cp1", ""),
    "effectif_primaire_public": ("Élèves du public", "élèves", PUBLIE, ""),
    "effectif_primaire_prive": ("Élèves du privé", "élèves", PUBLIE, ""),
    "effectif_primaire_urbain": ("Élèves en milieu urbain", "élèves", PUBLIE, ""),
    "effectif_primaire_rural": ("Élèves en milieu rural", "élèves", PUBLIE, ""),
    **{f"effectif_{c}": (f"Élèves du {c.upper()}", "élèves", "public + privé (la feuille 4 ne détaille pas l'ensemble)", "")
       for c in ["cp1", "cp2", "ce1", "ce2", "cm1", "cm2"]},
    **{f"effectif_{c}_public": (f"Élèves du {c.upper()}, public", "élèves", PUBLIE, "")
       for c in ["cp1", "cp2", "ce1", "ce2", "cm1", "cm2"]},
    "effectif_prescolaire_public": ("Préscolaire public", "enfants", PUBLIE, ""),
    "effectif_prescolaire_prive": ("Préscolaire privé", "enfants", PUBLIE, ""),
    "effectif_prescolaire_communautaire": ("Préscolaire communautaire", "enfants", PUBLIE, ""),
    "effectif_prescolaire_urbain": ("Préscolaire urbain", "enfants", PUBLIE, "Non publié avant 2017-2018"),
    "effectif_prescolaire_rural": ("Préscolaire rural", "enfants", PUBLIE, "Non publié avant 2017-2018"),
    "effectif_petite_section": ("Petite section", "enfants", "somme des trois statuts", ""),
    "effectif_moyenne_section": ("Moyenne section", "enfants", "somme des trois statuts", ""),
    "effectif_grande_section": ("Grande section", "enfants", "somme des trois statuts", ""),
    "part_prive_primaire": ("Part des élèves du privé", "proportion", "effectif_primaire_prive / effectif_primaire", ""),
    "part_urbain_primaire": ("Part des élèves en milieu urbain", "proportion", "effectif_primaire_urbain / effectif_primaire", ""),
    "rapport_cm2_cp1_national": ("Rapport CM2 / CP1", "rapport", "effectif_cm2 / effectif_cp1", ""),
}

# Variables propres au panel mensuel, absentes de VARIABLES.
DESCRIPTIONS_MENSUEL = {
    "mois": ("identifiant", "Mois de la situation des déplacés", "SP/CONASUR"),
    "date_situation": ("identifiant", "Date exacte de la situation retenue pour le mois", "SP/CONASUR"),
    "enfants_deplaces": ("explicative", "Enfants parmi les déplacés accueillis", "SP/CONASUR"),
    "variation_un_releve": ("explicative", "Évolution des déplacés depuis le relevé précédent", "SP/CONASUR ; calculs des auteurs"),
    "variation_trois_releves": ("explicative", "Évolution des déplacés sur trois relevés", "SP/CONASUR ; calculs des auteurs"),
}

# Tables : description, grain, clé primaire, usage.
TABLES = {
    "panel_province_annee": ("Base du modèle d'abandon : cible et variables connues à la rentrée de t",
                             "province (45) × année scolaire t", ["province_ancienne_pcode", "annee_scolaire"],
                             "Entraînement et prévision du modèle d'abandon ; carte du risque"),
    "panel_mensuel_province": ("Déplacés par province et par relevé, avec leurs évolutions, et écoles fermées de la région",
                               "province × mois", ["province_ancienne_pcode", "mois"],
                               "Alerte mensuelle entre deux annuaires"),
    "panel_region_annee": ("Indicateurs régionaux de la base principale DGESS, préscolaire et primaire",
                           "région (13) et pays × année scolaire", ["region_ancienne_pcode", "annee_scolaire"],
                           "Contexte régional du modèle ; comparaison entre régions"),
    "serie_nationale_annee": ("Indicateurs nationaux et ventilations publiées seulement au niveau national",
                              "année scolaire", ["annee_scolaire"], "Cadrage national, cohérence des agrégats"),
}

# Clés étrangères : table, colonnes, table cible, colonnes cibles.
LIENS = [
    ("panel_province_annee", ["region_ancienne_pcode", "annee_scolaire"], "panel_region_annee",
     ["region_ancienne_pcode", "annee_scolaire"]),
    ("panel_mensuel_province", ["province_ancienne_pcode"], "panel_province_annee", ["province_ancienne_pcode"]),
    ("panel_region_annee", ["annee_scolaire"], "serie_nationale_annee", ["annee_scolaire"]),
]
