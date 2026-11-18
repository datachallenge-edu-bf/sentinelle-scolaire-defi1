# Sentinelle Scolaire : application

Tableau de bord du risque de décrochage scolaire au primaire, par province du Burkina Faso (47 provinces, 17 régions, découpage de 2025).

- `api/` : API FastAPI. Elle sert les sorties de l'étape 04 (`data/04_analyse/`) et les modèles sauvegardés. Elle produit aussi les rapports PDF, la mise à jour annuelle et l'assistant.
- `web/` : site Next.js (React). La carte utilise MapLibre GL JS, sans tuiles externes, avec les contours de `data/02_nettoyage/contours_web/`. Les graphiques utilisent Apache ECharts.
- `guide/` : guide d'utilisation en PDF (`guide.py`), publié dans `web/public/guide_sentinelle.pdf`.

## Écrans

| Écran | Contenu |
|---|---|
| Vue nationale | Curseur des années (2024-2025 observé, prévisions 2025-2026 à 2027-2028), chiffres clés, carte des classes et des alertes de rupture, nuage SHAP signé, classement des 47 provinces en trois graphiques, filles et garçons, provinces qui résistent, classes d'une année à l'autre |
| Fiche province | Taux observé et prévu, intervalle, rang, score de rupture, historique et prévisions, facteurs SHAP, filles et garçons |
| Vue régions | Carte, classement des régions, provinces de la région choisie |
| Simulateur de leviers | Taux attendu d'une province quand ses caractéristiques changent (elastic net sauvegardé) |
| Mise à jour des données | Saisie ou import des données d'une nouvelle année, contrôles, nouvelles prévisions, enregistrement à part |
| Alertes (panneau) | Provinces en alerte de rupture et provinces en risque élevé en hausse |
| Assistant (bulle) | Questions de décision, réponses tirées des données, avec sources et liens |

Chaque écran propose trois vues : ensemble, filles ou garçons. Le choix est gardé dans l'adresse (`?population=F`).
Les boutons « Rapport » produisent un PDF national, régional ou provincial.

## Lancer

Prérequis :
- l'environnement Python du projet (`requirements.txt`) ;
- Node.js 20 ou plus récent ;
- les sorties de l'étape 04 (`sentinelle.analyse.executer_modelisation()`).

```bash
# 1. API (port 8000), depuis defi1_sentinelle/application/api
python -m uvicorn main:app --port 8000

# 2. Site (port 3000), depuis defi1_sentinelle/application/web
npm install
npm run build
npm start
```

Ouvrir http://localhost:3000. La documentation de l'API est sur http://localhost:8000/docs.
Le site relaie `/api/*` vers l'API. Pour une API placée ailleurs, définir `SENTINELLE_API` avant `npm run build`.

Assistant : sans configuration, il répond en mode hors ligne. Pour que les réponses soient rédigées par Gemini, définir la clé avant de lancer l'API (`GEMINI_API_KEY=...` ; modèle modifiable par `GEMINI_MODELE`). La clé n'est jamais écrite dans le code. Seuls des taux agrégés par province sont transmis.

Guide : depuis `application/guide`, `python guide.py` régénère `web/public/guide_sentinelle.pdf`.

## Déployer

**Sur un ordinateur Windows, sans Internet (finale).** Double-cliquer `lancer.bat`. Au premier lancement, le script installe et construit le site. Il démarre ensuite l'API et le site, puis ouvre le navigateur. L'assistant répond en mode hors ligne.

**Avec Docker, sur n'importe quelle machine.** Depuis `application/` : `docker compose up --build`, puis ouvrir http://localhost:3000. L'image unique (`Dockerfile`) contient l'API, le site, le code d'analyse et les seules sorties nécessaires (`data/02_nettoyage/contours_web`, `data/03_transformation/base_apuree`, `data/04_analyse`). Les versions Python de `requirements-api.txt` sont celles qui ont produit les modèles sauvegardés.

**En ligne (Railway).** Voir `DEPLOIEMENT.md` : `python preparer_deploiement.py` assemble un dossier de 10 Mo, puis `railway up` l'envoie. Plus généralement, la même image peut être déployée telle quelle sur un hébergeur de conteneurs : Hugging Face Spaces en Docker (port 7860 par défaut, variable `PORT`), Render ou Railway. La clé Gemini se déclare en secret (`GEMINI_API_KEY`). Avant toute publication, vérifier que le règlement du concours l'autorise.

## Points d'accès de l'API

| Adresse | Réponse |
|---|---|
| `GET /api/meta` | Années, populations, provinces, régions, sources |
| `GET /api/carte` | Contours des provinces et des régions, points d'étiquette |
| `GET /api/national?population=` | Série des quatre années par province, alertes, filles et garçons par région, nuage SHAP, provinces qui résistent, erreurs au test |
| `GET /api/province/{pcode}?population=` | Fiche complète d'une province |
| `GET /api/simulateur/{pcode}`, `POST /api/simulateur` | Leviers d'une province, taux attendu pour un scénario |
| `POST /api/assistant` | Réponse de l'assistant |
| `GET /api/rapport/national`, `/api/rapport/region/{nom}`, `/api/rapport/province/{pcode}` | Rapports PDF |
| `GET /api/mise_a_jour/etat`, `GET /api/mise_a_jour/modele.csv` | État des données, fichier à remplir |
| `POST /api/mise_a_jour/lire`, `/apercu`, `/enregistrer` | Lecture d'un CSV, aperçu des prévisions, enregistrement |
| `GET /api/mise_a_jour/previsions/{annee}.csv`, `DELETE /api/mise_a_jour/{annee}` | Prévisions d'une année saisie, retrait de la dernière année |

`population` vaut `ensemble` (par défaut), `F` ou `G`.

## Lecture des chiffres

- **Années.** Le taux de l'année t est mesuré entre t-1 et t. 2024-2025 est observé. 2025-2026, 2026-2027 et 2027-2028 sont prévus à 1, 2 et 3 ans, avec des intervalles validés.
- **Modèle de prévision.** Retour amorti vers le niveau habituel : l'écart de 2024-2025 au niveau habituel (échelle logit) se résorbe d'un facteur φ par an (φ = 0,2 pour l'ensemble, 0,3 par sexe). Il a été retenu parmi dix modèles selon la règle de `prevision.choisir_modele`, sur les plis de sélection seulement. Les marges de l'intervalle ne diminuent pas avec l'horizon.
- **Intervalle.** Conforme, à 80 %, calculé en logit puis ramené en pourcentage. Il est donc asymétrique et reste entre 0 et 100 %.
- **Classes de risque.** Seuils de `fiche_modele.json` : la classe moyen commence à la médiane des taux prévus, la classe élevé au 80e centile.
- **Provinces qui résistent.** Niveau habituel observé comparé au niveau attendu d'après les caractéristiques. L'attendu est prédit par un LightGBM qui n'a pas vu la province (validation croisée par groupes).
- **Mise à jour.** Elle reprend le modèle retenu (niveau habituel hors années de rupture, retour amorti avec le φ sauvegardé), les marges et les seuils sauvegardés, et recalcule le modèle d'alerte sur les nouveaux signaux. Le résultat reproduit exactement les sorties de l'analyse. Les données saisies vont dans `data/05_mises_a_jour/` et ne modifient pas les données officielles.
- **Facteurs et simulateur.** Ce sont des associations entre provinces, pas des causes.
