# Sources des données du prototype

## Données réelles
- `indicateurs_regions_2024_2025.csv` : DGESS/MEBAPLN, *Annuaire statistique de l'enseignement primaire 2024/2025*, juillet 2025, tableaux I.5 (taux brut de scolarisation) et II.7 (taux d'achèvement), public + privé, 13 régions.
  https://www.education.gov.bf/fileadmin/user_upload/storages/annuaire_statistique_du_primaire_2024-2025_vf.pdf
- `fermetures_ecoles.csv` : rapports du ST-ESU relayés par la presse et l'UNICEF (voir colonne `source`) ; compilation des auteurs.
- `provinces_bfa_45.geojson`, `regions_bfa_13.geojson` : contours Natural Earth (paquet npm `datamaps`), provinces regroupées en 13 régions par les auteurs. Contours simplifiés, à usage d'illustration.

## Données fictives
- `ecoles_fictives.csv`, `eleves_fictifs.csv` : générées par `scripts/generer_donnees_fictives.py`. **Aucun élève réel.** Elles servent uniquement à illustrer les vues école et élève.
