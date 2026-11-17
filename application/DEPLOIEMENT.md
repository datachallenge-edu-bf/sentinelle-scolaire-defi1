# Déployer Sentinelle Scolaire sur Railway

L'application tourne dans un conteneur unique : l'API FastAPI en interne, le site Next.js exposé. Railway construit l'image à partir du `Dockerfile`. Il fournit une adresse publique en HTTPS, et le service ne se met pas en veille.

Le code et les données ne sont pas publiés : on envoie à Railway un dossier assemblé, sans passer par un dépôt public. Seuls les résultats affichés par l'application sont visibles. La documentation interactive de l'API est fermée en production.

## 1. Préparer le dossier à envoyer

Depuis `defi1_sentinelle/application` :

```bash
python preparer_deploiement.py
```

Le script crée `application/deploiement/` (environ 10 Mo, ignoré par Git), qui contient :
- le code d'analyse ;
- l'API ;
- le site ;
- les seules sorties utiles : contours, base apurée, résultats de l'étape 04 ;
- `Dockerfile` et `railway.json`.

Il faut relancer ce script après chaque modification de l'application ou des résultats.

## 2. Installer l'outil Railway et se connecter (une seule fois)

```bash
npm install -g @railway/cli
railway login
```

`railway login` ouvre le navigateur. On s'y connecte avec un compte Railway, créé avec GitHub ou une adresse e-mail.

## 3. Créer le projet et envoyer l'application

```bash
cd deploiement
railway init        # nom du projet : sentinelle-scolaire
railway up          # envoie le dossier, construit l'image et la lance
```

La première construction prend environ 10 minutes : installation des bibliothèques Python, puis construction du site. Les journaux défilent dans le terminal et sur railway.com.

## 4. Régler le service sur railway.com

Dans le projet, ouvrir le service, puis :

1. **Variables**, puis **New Variable** : `GEMINI_API_KEY` = ta clé. La clé est collée ici, jamais dans un fichier. Sans clé, l'assistant répond en mode hors ligne.
2. **Settings**, puis **Networking**, puis **Generate Domain**. Railway propose une adresse du type `https://sentinelle-scolaire-production.up.railway.app`, que l'on peut renommer, par exemple `sentinelle-scolaire.up.railway.app`. Si un port est demandé, indiquer `7860`.
3. **Settings**, puis **Resources** : prévoir au moins 2 Go de mémoire (LightGBM, SHAP et GeoPandas sont chargés au premier appel).

L'application est alors en ligne. Le premier affichage peut prendre quelques secondes, le temps de charger les modèles.

## 5. Mettre à jour la version en ligne

```bash
cd application
python preparer_deploiement.py
cd deploiement
railway up
```

## Nom de domaine (facultatif)

Dans **Settings**, puis **Networking**, puis **Custom Domain** : saisir le domaine acheté (par exemple `sentinelle-scolaire.com`), puis recopier chez le vendeur du domaine l'enregistrement DNS affiché par Railway. Le certificat HTTPS est fourni automatiquement.

## À savoir

- **Données saisies en ligne.** Les données saisies dans « Mise à jour des données » sont rangées dans le conteneur et perdues à chaque redéploiement. La version en ligne sert à la démonstration ; les mises à jour réelles se font sur le poste du service statistique.
- **Coût.** Railway facture la mémoire et le processeur consommés. Le crédit d'essai couvre la période du concours. Ensuite, compter quelques dollars à une quinzaine de dollars par mois, selon les tarifs en vigueur.
- **Sans Internet**, par exemple le jour de la finale : `lancer.bat` (Windows) ou `docker compose up --build`.
