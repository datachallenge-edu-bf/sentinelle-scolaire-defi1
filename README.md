# Sentinelle Scolaire : Data Challenge Burkina 2026, défi 1

Cartographie et anticipation du risque de décrochage scolaire au primaire, à partir des données remises par les organisateurs.

## Organisation

Le projet est rangé dans le dossier des données remises par les organisateurs, qu'il lit sans jamais les modifier : le code refuse d'écrire dans `DataPack_DCB_2026`, la base principale et le document du challenge.

```
Competition_EducationBurkina/
├── DataPack_DCB_2026/, base principale, document du challenge   (organisateurs, lecture seule)
├── defi1_sentinelle/               ce projet
└── defi3_boussole/                 projet du défi 3 (autre équipe)
```

| Élément | Contenu |
|---|---|
| `src/sentinelle/` | Code de la chaîne de traitement, un sous-module par étape |
| `notebooks/` | Un notebook numéroté par étape, enregistré avec ses résultats |
| `data/` | Sorties de la chaîne : extraits bruts (01), base nettoyée (02) |
| `depots/` | Fichiers à déposer sur la plateforme, nommés selon la convention du challenge |
| `docs/` | Documentation (méthodologie de collecte et de nettoyage) |
| `outputs/` | Figures et cartes |
| `prototype/` | Prototype de la note d'intention (application web). Ses fichiers `prototype/data/` sont en partie **simulés** : la chaîne de traitement ne les lit jamais |
| `docs/note_intention/` | Note d'intention du défi 1 et sa source LaTeX |

## Étapes

| Étape | Module | Notebook | Sorties |
|---|---|---|---|
| 01 Collecte | `sentinelle.collecte` | `notebooks/01_collecte.ipynb` | `data/01_collecte/`, `depots/01-collecte/` |
| 02 Nettoyage | `sentinelle.nettoyage` | `notebooks/02_nettoyage.ipynb` | `data/02_nettoyage/` (base GeoPackage), `depots/02-nettoyage/` |
| 03 Transformation | `sentinelle.transformation` | `notebooks/03_transformation.ipynb` | `data/03_transformation/` (table d'analyse province × année, panel mensuel, indicateurs régionaux et série nationale de la base principale), `depots/03-transformation/` |

## Démarrer après un clonage

Le dépôt contient les données produites par la chaîne (`data/` et `depots/`), prêtes à consulter et à déposer. Il ne contient pas les données des organisateurs, réservées au concours : elles ne sont nécessaires que pour relancer la chaîne.

1. Récupérer dans l'espace du challenge le Data Pack (`DataPack_DCB_2026/`) et la base principale (`DONNEES_STATISTQUES_ PRESCOLAIRE ET PRIMAIRE_2016_2025_DCB.xlsx`), et les placer dans un dossier `Competition_EducationBurkina/`.
2. Cloner le dépôt dans ce même dossier :
   ```powershell
   cd Competition_EducationBurkina
   git clone https://github.com/datachallenge-edu-bf/sentinelle-scolaire-defi1.git defi1_sentinelle
   ```
3. Pour relancer la chaîne, installer l'environnement (section suivante). Les dossiers `data/` et `depots/` sont recréés à l'identique.

## Relancer

Depuis ce dossier, avec Python 3.11 ou plus récent :

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:SENTINELLE_EQUIPE = "E07"     # code équipe utilisé dans le nom des dépôts
$env:PYTHONPATH = "src"
python -m sentinelle.collecte       # étape 01
python -m sentinelle.nettoyage      # étape 02
python -m sentinelle.transformation # étape 03
```

Si les données des organisateurs sont rangées ailleurs que dans le dossier parent, indiquer leur dossier par `$env:SENTINELLE_DONNEES`.

## La base principale DGESS

Le classeur `DONNEES_STATISTQUES_ PRESCOLAIRE ET PRIMAIRE_2016_2025_DCB.xlsx` est lu en entier (14 feuilles, 21 tableaux, 6 621 valeurs) dans la table `fait_base_principale` : effectifs du préscolaire et du primaire par région, statut, milieu, classe et sexe, nouveaux inscrits au CP1, TBA, TBS, taux d'achèvement, réussite au CEP, indices de parité, écoles, structures et salles du préscolaire. Le contexte de la région entre dans la table d'analyse ; `panel_region_annee` et `serie_nationale_annee` reprennent tous ses indicateurs.

## Éducation non formelle et préscolaire

Les annuaires de l'éducation non formelle (campagnes 2018, 2019, 2020 et 2024) et du préscolaire (2023-2024 et 2024-2025) sont lus par province dans `fait_enf_province` et `fait_prescolaire_province`. La campagne est lue dans l'en-tête des pages : deux fichiers du Data Pack sont identiques (CNS517 et CNS519, campagne 2020) et le second est écarté. Les adolescents de l'éducation non formelle et le taux de préscolarisation de la province entrent dans la table d'analyse.

## Métadonnées des bases du modèle

Les quatre tables d'analyse (`panel_province_annee`, `panel_mensuel_province`, `panel_region_annee`, `serie_nationale_annee`) sont décrites dans `data/03_transformation/metadonnees/`, régénéré à chaque exécution :

| Fichier | Contenu |
|---|---|
| `dictionnaire_bases_modele.csv` | Une fiche par variable : libellé, description, rôle, unité, type, plage ou modalités, part manquante, années, mode de calcul, source, limites |
| `tables_bases_modele.csv` | Une ligne par table : contenu, grain, clé, liens, usage, taille, période |
| `datapackage.json` | Les mêmes informations au format standard Frictionless Data Package (schémas, clés primaires et étrangères) |
| `dictionnaire_bases_modele.html` | Version lisible, à ouvrir dans un navigateur ou à imprimer en PDF |

Les libellés, unités, modes de calcul et limites sont rédigés dans `src/sentinelle/transformation/fiche.py` ; le contrôle `fiches_completes` vérifie qu'aucune variable n'en manque.

## Pauvreté et conditions de vie (RGPH 2019)

La table `fait_conditions_vie` reprend les 33 indicateurs du volume 3 du RGPH 2019 (INSD, *Mesure et cartographie de la pauvreté*, 2022) pour les 351 communes, les 45 provinces, les 13 régions et le pays, à partir du PDF du Data Pack (NADA275). Elle est comparée à l'extraction indépendante d'un membre de l'équipe (`Sentinelle_Scolaire_Pauvrete_INSD_2019.xlsx`, à placer dans `Competition_EducationBurkina/`) : 4 485 valeurs identiques sur 4 485. Onze de ces indicateurs entrent dans la table d'analyse comme caractéristiques structurelles de la province (mesure unique de 2019).

## Sources externes

Les annuaires régionaux 2024 de l'INSD pour le Centre-Est, le Centre-Nord et l'Est, absents du Data Pack, sont dans `Competition_EducationBurkina/sources_externes/` : PDF d'origine, CSV au format du Data Pack, manifeste (adresse, date, empreinte) et script de conversion `convertir_pdf.py`.

## Couverture de l'année 2024-2025

- Années : l'année scolaire 2024-2025 correspond, pour la population, à l'année civile de la rentrée (2024).
- Le tableau de bord DGESS 2025 donne les indicateurs du post-primaire et du secondaire par région et pour le
  pays jusqu'en 2024-2025 (table `fait_tableau_bord_secondaire`). Sa table des indicateurs clés indique un TBA
  du secondaire de 18,2 % en 2024-2025, contre 18,1 % dans le texte (pages 31-32) : la valeur du tableau est
  gardée et l'écart signalé.
- Un total national n'est jamais réparti entre provinces ou communes.
- Les annuaires régionaux de l'INSD s'arrêtent en 2023-2024 : dans le panel communal, les effectifs, enseignants
  et salles de 2024-2025 restent vides ; la population et le recensement y sont renseignés.
- Le fichier de déplacements de mai 2025 décrit des événements, pas un stock comparable aux situations du
  CONASUR, et le rapport ESU de mai 2025 donne des réouvertures par région : ni l'un ni l'autre ne prolonge
  les séries existantes.

Le détail de cette vérification est dans `Competition_EducationBurkina/audit_couverture_2025/`.
