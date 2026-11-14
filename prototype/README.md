# Sentinelle Scolaire : prototype (Défi 1)

Tableau de bord de démonstration à quatre niveaux : région, école, élève, agent conversationnel.

- **Vue Région : données réelles** (DGESS, annuaire statistique 2024-2025 ; fermetures d’établissements : rapports ST-ESU).
- **Vues École, Élève, Agent : données fictives**, générées et calibrées sur les taux réels. Aucun élève réel.

## Lancer (VS Code ou terminal)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python scripts/generer_donnees_fictives.py   # écoles et élèves fictifs
python scripts/entrainer_modele.py           # modèle explicable + scores
streamlit run app.py                         # ouvre http://localhost:8501 (ou double-cliquer sur web/sentinelle_scolaire.html)
```

Les fichiers de `data/` sont déjà fournis : les deux scripts ne sont nécessaires que pour régénérer.

## Contenu de `data/`

| Fichier | Nature | Origine |
|---|---|---|
| `regions_bfa_13.geojson`, `provinces_bfa_45.geojson` | réel | contours Natural Earth (paquet npm datamaps), agrégés en 13 régions par `scripts/preparer_contours.py` |
| `indicateurs_regions_2024_2025.csv` | réel | DGESS (2025), annuaire statistique, tableaux I.5 et II.7 |
| `fermetures_ecoles.csv` | réel | rapports ST-ESU relayés par la presse et l’UNICEF |
| `ecoles_fictives.csv`, `eleves_scores.csv` | **fictif** | `generer_donnees_fictives.py`, `entrainer_modele.py` |
| `modele_metriques.json` | sur données fictives | `entrainer_modele.py` |

Voir `data/SOURCES.md` pour les références détaillées.

## Passage aux données réelles

Quand les organisateurs fourniront les données (base de la campagne statistique, fichier élèves pseudonymisé, rapports ST-ESU) :
remplacer `ecoles_fictives.csv` et la table élèves par les vraies tables en gardant les mêmes noms de colonnes, puis relancer `entrainer_modele.py`.
L’application ne change pas.

## Mise en ligne (facultatif)

Streamlit Community Cloud (gratuit) : pousser le dossier sur un dépôt GitHub **créé avec un compte neutre** (évaluation anonyme), puis « New app » → `app.py`.
