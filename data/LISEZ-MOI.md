# Dossier de travail de la chaîne de traitement

Ce dossier contient les sorties de chaque étape, sous des noms courts que le code relit d'une étape à l'autre :

| Dossier | Étape | Module qui l'écrit |
|---|---|---|
| `01_collecte/` | Collecte : extractions brutes, registre des sources | `sentinelle.collecte` |
| `02_nettoyage/` | Nettoyage : base GeoPackage, tables propres, journal, contrôles, contours | `sentinelle.nettoyage` |
| `03_transformation/` | Transformation : table d'analyse, panels, base apurée, dictionnaires | `sentinelle.transformation`, `sentinelle.apurement` |
| `04_analyse/` | Analyse : exploration, prévisions, fiabilité, modèles sauvegardés | `sentinelle.analyse` |
| `05_interpretation/` | Interprétation : indicateurs clés, carte d'alerte, rapports PDF | `sentinelle.interpretation` |

**Les fichiers à déposer sur la plateforme ne sont pas ici** : ils sont dans `../depots/`, renommés selon la
convention du challenge (`DiscernaTeam_ÉTAPE_D1_RÔLE_description_vN`), avec un LISEZ-MOI par dépôt. Chaque
commande d'étape les régénère à partir de ce dossier.
