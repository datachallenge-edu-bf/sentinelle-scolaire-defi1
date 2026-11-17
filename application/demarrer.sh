#!/bin/sh
# Démarrage dans le conteneur : l'API écoute en interne, le site est exposé sur $PORT et relaie /api/* vers l'API.
cd /app/application/api && python -m uvicorn main:app --host 127.0.0.1 --port 8000 &
cd /app/application/web && exec node node_modules/next/dist/bin/next start -H 0.0.0.0 -p "${PORT:-7860}"
