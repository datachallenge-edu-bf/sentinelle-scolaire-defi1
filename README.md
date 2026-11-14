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
