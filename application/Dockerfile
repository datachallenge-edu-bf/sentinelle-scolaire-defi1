# Sentinelle Scolaire : une seule image avec l'API (FastAPI, port interne 8000) et le site (Next.js).
# Construction depuis le dossier defi1_sentinelle :
#   docker build -f application/Dockerfile -t sentinelle .
#   docker run -p 3000:7860 -e GEMINI_API_KEY=... sentinelle      (puis http://localhost:3000)

FROM node:20-bookworm-slim AS site
WORKDIR /app/web
COPY application/web/package.json application/web/package-lock.json ./
RUN npm ci
COPY application/web/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build && npm prune --omit=dev

FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY --from=site /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY application/requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt
COPY src ./src
COPY data/02_nettoyage/contours_web ./data/02_nettoyage/contours_web
COPY data/03_transformation/base_apuree ./data/03_transformation/base_apuree
COPY data/03_transformation/dictionnaire_variables_modele.csv ./data/03_transformation/
COPY data/03_transformation/metadonnees/dictionnaire_bases_modele.csv ./data/03_transformation/metadonnees/
COPY data/04_analyse ./data/04_analyse
COPY application/api ./application/api
COPY application/demarrer.sh ./application/demarrer.sh
COPY --from=site /app/web ./application/web
ENV PORT=7860 NEXT_TELEMETRY_DISABLED=1 PYTHONIOENCODING=utf-8 MPLCONFIGDIR=/tmp/matplotlib SENTINELLE_PRODUCTION=1
RUN useradd -m sentinelle && mkdir -p /app/data/05_mises_a_jour && chown -R sentinelle /app/data/05_mises_a_jour
USER sentinelle
EXPOSE 7860
CMD ["sh", "/app/application/demarrer.sh"]
