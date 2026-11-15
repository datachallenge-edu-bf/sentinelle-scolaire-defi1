"""Catalogue des jeux de données collectés pour le défi 1.

Chaque jeu regroupe un ou plusieurs CSV du Data Pack et une règle qui dit
quelles pages en extraire. Les lignes retenues sont copiées sans modification :
la remise en forme relève de l'étape 02 (nettoyage).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Regle:
    """Règle de sélection des pages d'un CSV issu d'un PDF.

    mode
        « tout » : toutes les lignes du fichier.
        « entete » : pages dont l'en-tête (premières lignes) correspond au motif ;
        une page dont l'en-tête correspond au motif d'exclusion est écartée.
        « texte » : pages dont une ligne quelconque correspond au motif ;
        les lignes correspondant au motif d'exclusion sont ignorées.
    """

    mode: str = "tout"
    motif: str | None = None
    lignes_entete: int = 4
    ignorer_casse: bool = False
    exclure: str | None = None
    continuation: bool = False

    def __post_init__(self) -> None:
        if self.mode not in {"tout", "entete", "texte"}:
            raise ValueError(f"Mode inconnu : {self.mode}")
        if self.mode != "tout" and not self.motif:
            raise ValueError("Un motif est requis pour les modes « entete » et « texte ».")


@dataclass(frozen=True)
class Jeu:
    """Jeu de données à collecter."""

    identifiant: str
    libelle: str
    theme: str
    niveau_geo: str
    fichiers: tuple[str, ...]
    regle: Regle = field(default_factory=Regle)
    exclure_fichiers: str | None = None
    periode: str = ""
    usage: str = ""


ANNUAIRES_PRIMAIRE = (
    "01_Education_MENAPLN_DGESS/CNS_DGESS/Annuaires/CNS52[1-6]_*rimaire*.csv",
    "01_Education_MENAPLN_DGESS/CNS_DGESS/Annuaires/CNS529_*rimaire*.csv",
    "01_Education_MENAPLN_DGESS/CNS_DGESS/Annuaires/CNS530_*rimaire*.csv",
)

ANNUAIRES_COMMUNES_PRIORITAIRES = (
    "01_Education_MENAPLN_DGESS/CNS_DGESS/Annuaires/CNS52[1-4]_*rimaire*.csv",
)

# Périodes que le nom du fichier ne permet pas de déduire, relevées dans le document lui-même.
PERIODES_CONNUES = {
    "RAPPORT_STATISTIQUE_Mensuel_ESU_Novembre.pdf": "2024-11",  # en-tête : « novembre 2024 »
    "idps4.xlsx": "plusieurs dates (colonne date)",
}

TABLES_DES_MATIERES = r"\.{4,}|…"
COMMUNES_PRIORITAIRES = r"COMMUNES PRIORITAIRES|^PRIORITAIRES"

CATALOGUE: tuple[Jeu, ...] = (
    # Éducation : cible et offre scolaire par province (DGESS).
    Jeu(
        identifiant="dgess_flux_province",
        libelle="Taux de promotion, redoublement et abandon par province, classe et sexe",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"TAUX DE PROMOTION, REDOUBLEMENT", exclure=COMMUNES_PRIORITAIRES),
        usage="Variable cible : taux d'abandon par province",
    ),
    Jeu(
        identifiant="dgess_effectifs_redoublants_province",
        libelle="Historique des effectifs et des redoublants par niveau et par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"HISTORIQUE DES EFFECTIFS ET DES REDOUBLANTS"),
        usage="Recalcul des taux de flux par la méthode de la cohorte reconstituée",
    ),
    Jeu(
        identifiant="dgess_effectifs_historique_province",
        libelle="Historique des effectifs par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"HISTORIQUE DES EFFECTIFS PAR PROVINCE"),
        usage="Évolution des effectifs, chocs d'effectifs",
    ),
    Jeu(
        identifiant="dgess_principaux_chiffres_province",
        libelle="Écoles, salles de classe, élèves, groupes pédagogiques et maîtres par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"NOMBRE D.ECOLES.{0,5}SALLES", exclure=COMMUNES_PRIORITAIRES),
        usage="Offre scolaire : élèves par classe, élèves par maître",
    ),
    Jeu(
        identifiant="dgess_taux_acces_province",
        libelle="Taux d'admission, de scolarisation et d'achèvement par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"TAUX (?:BRUT|NET) D|TAUX D.ACH", exclure=COMMUNES_PRIORITAIRES),
        usage="Accès et achèvement, analysés à part de l'abandon",
    ),
    Jeu(
        identifiant="dgess_distance_province",
        libelle="Pourcentage des élèves selon la distance parcourue par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"DISTANCE"),
        usage="Éloignement de l'école",
    ),
    Jeu(
        identifiant="dgess_ecoles_salles_province",
        libelle="Répartition des écoles et salles de classe publiques et privées par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"REPARTITION DES ECOLES ET (?:DES )?SALLES"),
        usage="Offre scolaire",
    ),
    Jeu(
        identifiant="dgess_cep_province",
        libelle="Résultats au certificat d'études primaires par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"CERTIFICAT"),
        usage="Résultats scolaires",
    ),
    # Préscolaire : la fréquentation avant le CP1 prépare l'entrée et le maintien à l'école.
    Jeu(
        identifiant="dgess_prescolaire",
        libelle="Préscolaire : annuaires 2023-2024 et 2024-2025, dépliants et tableaux de bord",
        theme="education",
        niveau_geo="region et province",
        fichiers=(
            "01_Education_MENAPLN_DGESS/CNS_DGESS/Annuaires/CNS52[78]_*.csv",
            "01_Education_MENAPLN_DGESS/CNS_DGESS/Depliants/CNS53[89]_*.csv",
            "01_Education_MENAPLN_DGESS/CNS_DGESS/Tableaux_de_bord/CNS554_*.csv",
            "01_Education_MENAPLN_DGESS/CNS_DGESS/Tableaux_de_bord/CNS563_*.csv",
        ),
        usage="Préparation à l'école : enfants inscrits, structures, encadrement, par province",
    ),
    # Éducation non formelle : centres d'éducation de base (CEBNF), alphabétisation, passerelles.
    # Elle accueille des enfants et adolescents non scolarisés ou déscolarisés : l'autre versant
    # du décrochage.
    Jeu(
        identifiant="dgess_non_formelle_annuaires",
        libelle="Éducation non formelle : annuaires statistiques 2018 à 2021 et 2024",
        theme="education",
        niveau_geo="region et province",
        fichiers=("01_Education_MENAPLN_DGESS/CNS_DGESS/Annuaires/CNS51[6-9]_*.csv", "01_Education_MENAPLN_DGESS/CNS_DGESS/Annuaires/CNS520_*.csv"),
        usage="Offre de seconde chance pour les déscolarisés : centres, apprenants, par province",
    ),
    Jeu(
        identifiant="dgess_non_formelle_syntheses",
        libelle="Éducation non formelle : dépliants, synthèses et tableaux de bord 2015 à 2024",
        theme="education",
        niveau_geo="national et region",
        fichiers=(
            "01_Education_MENAPLN_DGESS/CNS_DGESS/Depliants/CNS54[0-6]_*.csv",
            "01_Education_MENAPLN_DGESS/CNS_DGESS/Syntheses/CNS53[12]_*.csv",
            "01_Education_MENAPLN_DGESS/CNS_DGESS/Tableaux_de_bord/CNS55[5-9]_*.csv",
            "01_Education_MENAPLN_DGESS/CNS_DGESS/Tableaux_de_bord/CNS56[0-2]_*.csv",
        ),
        usage="Séries longues de l'éducation non formelle, contrôle des totaux des annuaires",
    ),
    # Conditions de scolarisation par province (annuaires DGESS, 8 éditions) : une ligne par province.
    Jeu(
        identifiant="dgess_equipement_province",
        libelle="Écoles disposant d'eau potable, d'électricité, de latrines, de cantines, par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"EQUIPEMENT DES ECOLES", lignes_entete=6, exclure=COMMUNES_PRIORITAIRES),
        usage="Cantines, latrines, eau, électricité : conditions qui retiennent les élèves",
    ),
    Jeu(
        identifiant="dgess_taille_ecoles_province",
        libelle="Écoles selon le nombre de salles de classe fonctionnelles, par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"TAILLE DES [EÉé]COLES", lignes_entete=6, ignorer_casse=True),
        usage="Écoles à cycle incomplet (moins de six salles) : départ forcé en cours de cycle",
    ),
    Jeu(
        identifiant="dgess_logements_maitres_province",
        libelle="Maîtres, écoles sans logement de maître, logements et leur état, par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"ECOLES DISPOSANT DE LOGEMENTS? DE MA", lignes_entete=6, ignorer_casse=True),
        usage="Stabilité des enseignants dans les zones rurales",
    ),
    Jeu(
        identifiant="dgess_manuels_mobilier_province",
        libelle="Manuels des élèves et mobilier (tables-bancs, déficit de places assises), par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"MANUELS (DES )?ELEVES|MOBILIERS? (DES )?ELEVES", lignes_entete=6, ignorer_casse=True),
        usage="Conditions matérielles d'apprentissage",
    ),
    Jeu(
        identifiant="dgess_profession_parents_province",
        libelle="Élèves selon la profession des parents, par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"EFFECTIF DES ELEVES SELON LA PROFESSION DES PARENTS", lignes_entete=6),
        usage="Part des familles d'agriculteurs et d'éleveurs : travaux saisonniers et transhumance",
    ),
    Jeu(
        identifiant="dgess_salles_province",
        libelle="Salles de classe : surface, année de mise en service, nature et état des murs et des toitures, par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"SURFACE DES SALLES|ANNEE DE MISE EN SERVICE|NATURE ET ETAT DES (MURS|TOITURES)",
                    lignes_entete=6, ignorer_casse=True),
        usage="Salles précaires (paille, banco), anciennes ou exiguës",
    ),
    Jeu(
        identifiant="dgess_ages_province",
        libelle="Élèves et nouveaux entrants au CP1 par âge et sexe, par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"REPARTITION DES ELEVES PAR AGE ET SEXE|NOUVEAUX ENTRANTS PAR AGE", lignes_entete=6),
        usage="Retard scolaire (élèves plus âgés que l'âge officiel) et entrée tardive au CP1",
    ),
    Jeu(
        identifiant="dgess_enseignants_province",
        libelle="Enseignants par sexe, âge et nombre d'années d'expérience, par province",
        theme="education",
        niveau_geo="province",
        fichiers=ANNUAIRES_PRIMAIRE,
        regle=Regle("entete", r"NOMBRE D.?ANNEE D.?EXPERIENCE", lignes_entete=6),
        usage="Part des enseignantes et des enseignants débutants",
    ),
    Jeu(
        identifiant="dgess_communes_prioritaires",
        libelle="Principaux chiffres des 43 communes prioritaires (annuaires 2017-2018 à 2020-2021)",
        theme="education",
        niveau_geo="commune",
        fichiers=ANNUAIRES_COMMUNES_PRIORITAIRES,
        regle=Regle("entete", r"COMMUNES PRIORITAIRES|^PRIORITAIRES"),
        usage="Indicateurs communaux DGESS, dont flux, sur une partie du territoire",
    ),
    Jeu(
        identifiant="dgess_tableaux_de_bord_primaire",
        libelle="Tableaux de bord de l'enseignement primaire 2015-2016 à 2023-2024",
        theme="education",
        niveau_geo="region",
        fichiers=(
            "01_Education_MENAPLN_DGESS/CNS_DGESS/Tableaux_de_bord/CNS56[5-9]_*rimaire_*.csv",
            "01_Education_MENAPLN_DGESS/CNS_DGESS/Tableaux_de_bord/CNS57[0-4]_*rimaire_*.csv",
        ),
        usage="Séries régionales d'abandon, de redoublement et d'achèvement ; contrôle des totaux",
    ),
    Jeu(
        identifiant="dgess_tableaux_de_bord_post_primaire",
        libelle="Tableaux de bord du post-primaire et du secondaire 2023 et 2024",
        theme="education",
        niveau_geo="region",
        fichiers=("01_Education_MENAPLN_DGESS/CNS_DGESS/Tableaux_de_bord/CNS56[46]_*.csv",),
        usage="Transition du primaire vers le post-primaire",
    ),
    Jeu(
        identifiant="esu_rapports_mensuels",
        libelle="Rapports mensuels de l'éducation en situation d'urgence (ST-ESU)",
        theme="securite",
        niveau_geo="region et province",
        fichiers=("01_Education_MENAPLN_DGESS/ESU_Rapports_mensuels/*.csv",),
        exclure_fichiers=r"PDI",
        usage="Exposition sécuritaire : écoles fermées, rouvertes, délocalisées ; élèves déplacés",
    ),
    # Éducation par commune (annuaires statistiques régionaux de l'INSD).
    Jeu(
        identifiant="insd_primaire_commune",
        libelle="Écoles, salles, élèves et enseignants du primaire par commune (annuaires régionaux 2024, 13 régions)",
        theme="education",
        niveau_geo="commune",
        # Les annuaires 2024 du Centre-Est, du Centre-Nord et de l'Est, absents du Data Pack, ont été
        # téléchargés sur le site de l'INSD (sources externes, voir leur manifeste).
        fichiers=("02_Demographie_INSD/Annuaires_Statistiques_Regionaux_2024/*.csv",
                  "externe:insd_annuaires_regionaux_2024/*.csv"),
        regle=Regle(
            "texte",
            r"primaire.{0,80}commune|commune.{0,80}primaire|ferm\w* pour (?:cause d.)?ins[ée]curit",
            ignorer_casse=True,
            exclure=TABLES_DES_MATIERES + r"|post|secondaire|petite enfance|technique",
            continuation=True,
        ),
        usage="Variables communales agrégées par province : chocs d'effectifs, salles sous paillote",
    ),
    Jeu(
        identifiant="insd_post_primaire_commune",
        libelle="Établissements, salles, élèves et enseignants du post-primaire et du secondaire par commune "
                "(annuaires régionaux 2024, 13 régions)",
        theme="education",
        niveau_geo="commune",
        fichiers=("02_Demographie_INSD/Annuaires_Statistiques_Regionaux_2024/*.csv",
                  "externe:insd_annuaires_regionaux_2024/*.csv"),
        # Titres souvent coupés sur deux lignes : la page est retenue sur « post-primaire » ou « secondaire
        # général » ; le lecteur vérifie ensuite que le tableau est communal.
        regle=Regle("texte", r"post.?primaire|secondaire g[ée]n[ée]ral|du secondaire",
                    ignorer_casse=True, exclure=TABLES_DES_MATIERES + r"|technique|petite enfance|BEPC|BAC",
                    continuation=True),
        usage="Élèves du post-primaire par commune : clé de répartition des provinces scindées en 2025",
    ),
    Jeu(
        identifiant="insd_mines_region",
        libelle="Permis d'exploitation et sites miniers par typologie (industrielle, semi-mécanisée, artisanale), par région",
        theme="economie",
        niveau_geo="region",
        fichiers=("02_Demographie_INSD/Annuaires_Statistiques_Regionaux_2024/*.csv",
                  "externe:insd_annuaires_regionaux_2024/*.csv"),
        regle=Regle("texte", r"permis d.exploitation par typologie|site.? miniers? par typologie", ignorer_casse=True,
                    exclure=TABLES_DES_MATIERES),
        usage="Contexte minier régional, pour mémoire : série lacunaire, absente dans les régions de forte activité",
    ),
    # Sécurité et déplacements.
    Jeu(
        identifiant="pdi_conasur_commune",
        libelle="Personnes déplacées internes par commune (CONASUR), 2020 à 2025",
        theme="securite",
        niveau_geo="commune",
        fichiers=(
            "03_Conditions_de_Vie_et_Emploi/PDI_CONASUR/*.csv",
            "01_Education_MENAPLN_DGESS/ESU_Rapports_mensuels/*PDI*.csv",
        ),
        usage="Pression d'accueil et départs de population",
    ),
    # Démographie et conditions de vie.
    Jeu(
        identifiant="insd_projections_2020_2035",
        libelle="Projections démographiques 2020-2035 (RGPH 2019, volume 4)",
        theme="demographie",
        niveau_geo="region",
        fichiers=("02_Demographie_INSD/INSD_RGPH2019_Vol4_Projections_demographiques_2020-2035.csv",),
        usage="Dénominateurs : population d'âge scolaire",
    ),
    Jeu(
        identifiant="insd_profils_pauvrete",
        libelle="Profils régionaux de pauvreté (publiés en octobre 2023, mesure EHCVM 2018 et RGPH 2019)",
        theme="conditions_de_vie",
        niveau_geo="province et commune",
        fichiers=("03_Conditions_de_Vie_et_Emploi/Profils_pauvrete_regionaux/*.csv",),
        periode="2019",
        usage="Consommation par personne, sévérité de la pauvreté, inégalités (Gini) par province et commune",
    ),
    Jeu(
        identifiant="ehcvm_2021_education",
        libelle="EHCVM 2021, pages sur la scolarisation et l'abandon",
        theme="conditions_de_vie",
        niveau_geo="region",
        fichiers=("03_Conditions_de_Vie_et_Emploi/INSD_EHCVM_2021_Rapport_General.csv",),
        regle=Regle("texte", r"scolari|abandon|fr[ée]quentation", ignorer_casse=True,
                    exclure=TABLES_DES_MATIERES),
        usage="Déterminants socio-économiques",
    ),
    Jeu(
        identifiant="eds_2021_education_mariage",
        libelle="EDS 2021, pages sur l'instruction, la fréquentation scolaire et le mariage précoce",
        theme="conditions_de_vie",
        niveau_geo="region",
        fichiers=("03_Conditions_de_Vie_et_Emploi/EDS_2021_Rapport_final_DHS_FR378.csv",),
        regle=Regle("texte", r"mariage|scolari|fr[ée]quentation", ignorer_casse=True,
                    exclure=TABLES_DES_MATIERES),
        usage="Normes de genre et mariage précoce",
    ),
    Jeu(
        identifiant="rgph_cartographie_pauvrete",
        libelle="RGPH 2019 : cartographie de la pauvreté",
        theme="conditions_de_vie",
        niveau_geo="commune",
        fichiers=("02_Demographie_INSD/RGPH2019_NADA/NADA275_*.csv",),
        periode="2019",
        usage="Pauvreté par commune, agrégée par province",
    ),
    Jeu(
        identifiant="rgph_disparites_communales",
        libelle="RGPH 2019 : analyse des disparités communales",
        theme="conditions_de_vie",
        niveau_geo="commune",
        fichiers=("02_Demographie_INSD/RGPH2019_NADA/NADA272_*.csv",),
        periode="2019",
        usage="Indicateurs socio-démographiques par commune",
    ),
    Jeu(
        identifiant="rgph_alphabetisation_scolarisation",
        libelle="RGPH 2019 : rapport thématique alphabétisation et scolarisation",
        theme="education",
        niveau_geo="region",
        fichiers=("02_Demographie_INSD/INSD_RGPH2019_Rapport_Alphabetisation_Scolarisation.csv",),
        periode="2019",
        usage="Scolarisation selon le recensement, par sexe et milieu",
    ),
    Jeu(
        identifiant="rgph_localites",
        libelle="RGPH 2019 : fichier des localités (population par village et secteur)",
        theme="demographie",
        niveau_geo="localite",
        fichiers=("02_Demographie_INSD/RGPH2019_NADA/NADA270_*.csv",),
        periode="2019",
        usage="Demande scolaire locale et distance aux écoles",
    ),
    Jeu(
        identifiant="insd_annuaires_nationaux_education",
        libelle="Annuaires statistiques nationaux 2015-2024, pages sur l'enseignement primaire",
        theme="education",
        niveau_geo="region",
        fichiers=("02_Demographie_INSD/Annuaires_Statistiques_Nationaux/*.csv",),
        regle=Regle(
            "texte",
            r"enseignement primaire|primaire|scolarisation|abandon|ach[èe]vement|redoubl",
            ignorer_casse=True,
            exclure=TABLES_DES_MATIERES,
        ),
        usage="Séries régionales ; l'édition 2024 suit le découpage en 17 régions",
    ),
    Jeu(
        identifiant="insd_tableau_de_bord_social_2020",
        libelle="Tableau de bord social 2020 (INSD)",
        theme="conditions_de_vie",
        niveau_geo="region",
        fichiers=("03_Conditions_de_Vie_et_Emploi/INSD_Tableau_de_Bord_Social_2020.csv",),
        periode="2020",
        usage="Indicateurs sociaux régionaux sur dix ans",
    ),
    Jeu(
        identifiant="dgess_syntheses_primaire",
        libelle="Synthèses des annuaires de l'enseignement primaire 2017-2018 à 2021-2022",
        theme="education",
        niveau_geo="region",
        fichiers=("01_Education_MENAPLN_DGESS/CNS_DGESS/Syntheses/CNS53[3-7]_*primaire*.csv",),
        usage="Taux d'abandon, de redoublement et de promotion par région, pour recouper les annuaires",
    ),
    Jeu(
        identifiant="dgess_depliants_primaire",
        libelle="Dépliants statistiques de l'enseignement primaire 2017-2018 à 2023-2024",
        theme="education",
        niveau_geo="pays",
        fichiers=("01_Education_MENAPLN_DGESS/CNS_DGESS/Depliants/CNS5[45][0-9]_*primaire*.csv",),
        usage="Chiffres clés nationaux pour vérifier les totaux",
    ),
    Jeu(
        identifiant="dgess_annuaires_post_primaire",
        libelle="Annuaires statistiques du post-primaire et du secondaire 2018-2019 à 2022-2023",
        theme="education",
        niveau_geo="region et province",
        # 2019-2020 dans le Data Pack ; les quatre autres éditions fournies par l'équipe (sources externes).
        fichiers=("01_Education_MENAPLN_DGESS/Post_Primaire_Secondaire/*.csv",
                  "externe:dgess_post_primaire_secondaire/DGESS_Annuaire_*.csv"),
        periode="2018-2023",
        usage="Entrée en 6e, scolarisation, achèvement et abandons après le primaire, par province",
    ),
    # Référentiels géographiques.
    Jeu(
        identifiant="codab_communes",
        libelle="Limites administratives COD-AB : communes, avec anciens et nouveaux P-codes",
        theme="referentiel",
        niveau_geo="commune",
        fichiers=("04_Cartographie_SIG/COD-AB_limites_administratives/*__bfa_admin3.csv",),
        periode="2025-08",
        usage="Table de correspondance 13 et 17 régions, 45 et 47 provinces",
    ),
    Jeu(
        identifiant="codab_provinces",
        libelle="Limites administratives COD-AB : provinces",
        theme="referentiel",
        niveau_geo="province",
        fichiers=("04_Cartographie_SIG/COD-AB_limites_administratives/*__bfa_admin2.csv",),
        periode="2025-08",
    ),
    Jeu(
        identifiant="codab_regions",
        libelle="Limites administratives COD-AB : régions",
        theme="referentiel",
        niveau_geo="region",
        fichiers=("04_Cartographie_SIG/COD-AB_limites_administratives/*__bfa_admin1.csv",),
        periode="2025-08",
    ),
    Jeu(
        identifiant="ecoles_osm",
        libelle="Structures éducatives géolocalisées (OpenStreetMap, HOT)",
        theme="referentiel",
        niveau_geo="point",
        fichiers=("04_Cartographie_SIG/Ecoles_OSM_HOTOSM/*.csv",),
        periode="2026-11",
        usage="Localisation des écoles, distances",
    ),
    Jeu(
        identifiant="bm_unesco_series_nationales",
        libelle="Indicateurs éducation Banque mondiale et UNESCO, séries nationales",
        theme="education",
        niveau_geo="pays",
        fichiers=("01_Education_MENAPLN_DGESS/Series_longues_BM_UNESCO/*.csv",),
        periode="1970-2025",
        usage="Contrôle de cohérence des agrégats nationaux",
    ),
)


# Description employée dans le nom du fichier déposé : contenu, niveau géographique, période.
NOMS_DEPOT = {
    "dgess_base_principale": "base-principale-dgess-region-2016-2025",
    "insd_projections_actualisees": "population-age-simple-communes-provinces-pays-2007-2035",
    "dgess_flux_province": "taux-abandon-redoublement-province-2017-2025",
    "dgess_effectifs_redoublants_province": "effectifs-redoublants-classe-province-2017-2025",
    "dgess_effectifs_historique_province": "effectifs-historique-province-2017-2025",
    "dgess_principaux_chiffres_province": "ecoles-salles-maitres-province-2017-2025",
    "dgess_taux_acces_province": "taux-admission-scolarisation-achevement-province-2017-2025",
    "dgess_distance_province": "distance-ecole-province-2017-2025",
    "dgess_ecoles_salles_province": "ecoles-salles-public-prive-province-2017-2025",
    "dgess_cep_province": "resultats-cep-province-2017-2025",
    "dgess_communes_prioritaires": "indicateurs-43-communes-prioritaires-2017-2021",
    "dgess_equipement_province": "equipement-ecoles-eau-electricite-latrines-cantines-province-2017-2025",
    "dgess_taille_ecoles_province": "taille-ecoles-salles-fonctionnelles-province-2017-2025",
    "dgess_logements_maitres_province": "logements-maitres-province-2017-2025",
    "dgess_manuels_mobilier_province": "manuels-mobilier-eleves-province-2017-2025",
    "dgess_profession_parents_province": "eleves-profession-parents-province-2017-2025",
    "dgess_salles_province": "salles-surface-anciennete-etat-province-2017-2025",
    "dgess_ages_province": "eleves-nouveaux-entrants-par-age-province-2017-2025",
    "dgess_enseignants_province": "enseignants-sexe-age-experience-province-2017-2025",
    "dgess_prescolaire": "prescolaire-annuaires-depliants-tableaux-de-bord-2022-2025",
    "dgess_non_formelle_annuaires": "education-non-formelle-annuaires-2018-2024",
    "dgess_non_formelle_syntheses": "education-non-formelle-depliants-syntheses-2015-2024",
    "dgess_tableaux_de_bord_primaire": "tableaux-de-bord-primaire-region-2015-2024",
    "dgess_tableaux_de_bord_post_primaire": "tableaux-de-bord-post-primaire-region-2023-2024",
    "dgess_syntheses_primaire": "syntheses-annuaires-primaire-region-2017-2022",
    "dgess_depliants_primaire": "depliants-chiffres-cles-primaire-2017-2024",
    "dgess_annuaires_post_primaire": "annuaires-post-primaire-secondaire-2018-2023",
    "insd_post_primaire_commune": "post-primaire-secondaire-commune-insd-2014-2024",
    "esu_rapports_mensuels": "ecoles-fermees-esu-mensuel-2021-2026",
    "insd_primaire_commune": "ecoles-eleves-enseignants-commune-insd-2014-2024",
    "insd_mines_region": "permis-sites-miniers-typologie-region-2014-2024",
    "pdi_conasur_commune": "deplaces-internes-commune-2020-2025",
    "insd_projections_2020_2035": "projections-population-2020-2035",
    "insd_profils_pauvrete": "profils-pauvrete-region-province-2024",
    "insd_annuaires_nationaux_education": "annuaires-nationaux-insd-education-2015-2024",
    "insd_tableau_de_bord_social_2020": "tableau-de-bord-social-2020",
    "rgph_cartographie_pauvrete": "rgph-2019-pauvrete-commune",
    "rgph_disparites_communales": "rgph-2019-disparites-communales",
    "rgph_alphabetisation_scolarisation": "rgph-2019-alphabetisation-scolarisation",
    "rgph_localites": "rgph-2019-population-localites",
    "ehcvm_2021_education": "ehcvm-2021-scolarisation-abandon",
    "eds_2021_education_mariage": "eds-2021-instruction-mariage-precoce",
    "codab_communes": "referentiel-communes-pcodes-13-17-regions",
    "codab_provinces": "referentiel-provinces-pcodes",
    "codab_regions": "referentiel-regions-pcodes",
    "ecoles_osm": "ecoles-geolocalisees-osm-2026",
    "bm_unesco_series_nationales": "series-nationales-banque-mondiale-1970-2025",
}

# Fichiers du Data Pack examinés et non retenus, avec le motif de l'exclusion.
# La première règle dont le motif correspond au chemin s'applique.
SOURCES_ECARTEES: tuple[tuple[str, str], ...] = (
    (r"/Superieur/", "Enseignement supérieur : sans lien direct avec le décrochage au primaire"),
    (r"CNS758_", "Marché de l'emploi : sans lien direct avec le décrochage au primaire"),
    (r"ONG_et_AD", "Annuaires des ONG : interventions non reliées à la cible ; pistes de leviers pour plus tard"),
    (r"Dictionnaires_Questionnaires", "Documentation du RGPH : définitions citées, aucune donnée à extraire"),
    (r"NADA269_|NADA271_|NADA273_|CNS_RGPH2019_Synthese",
     "Résultats généraux du RGPH 2019 : chiffres repris plus finement par les autres publications retenues"),
    (r"NADA274_", "Caractéristiques des ménages (RGPH 2019) : niveau national et régional, redondant avec l'EHCVM"),
    (r"NADA276_", "Projections RGPH (NADA) : même contenu que le volume 4 des projections, retenu"),
    (r"NADA277_", "Évaluation de la qualité du RGPH : document méthodologique"),
    (r"bfa_admin0|admincapitals|adminlines|adminpoints|\.zip$|\.parquet$|\.html$|metadata\.json$",
     "Géométries et métadonnées cartographiques : utilisées à l'étape de cartographie, pas de tableau à collecter"),
    (r"Catalogue_sources_x_defis|manifeste_telechargements|LISEZ-MOI|Guide_du_Data_Pack|Document_du_challenge",
     "Documentation du challenge et du Data Pack : lue, sert à la traçabilité"),
)


def jeu(identifiant: str) -> Jeu:
    """Renvoie le jeu du catalogue portant cet identifiant."""
    for j in CATALOGUE:
        if j.identifiant == identifiant:
            return j
    raise KeyError(identifiant)
