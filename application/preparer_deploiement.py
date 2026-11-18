"""Assemble le dossier de déploiement de Sentinelle Scolaire (Railway ou tout hébergeur de conteneurs).

Le dossier ``deploiement/`` (à côté de ce script, ignoré par Git) ne contient que ce dont l'application a besoin :
le code d'analyse (``src/``), l'API, le site sans ses dépendances installées, et trois dossiers de sorties
(contours, base apurée, résultats de l'étape 04). Aucune donnée brute des organisateurs n'y figure.

Lancement, depuis ``application/`` : ``python preparer_deploiement.py``
"""

from __future__ import annotations

import shutil
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
CIBLE = ICI / "deploiement"
ELEMENTS = [
    "src/sentinelle",
    "application/api",
    "application/web",
    "application/demarrer.sh",
    "application/requirements-api.txt",
    "data/02_nettoyage/contours_web",
    "data/02_nettoyage/fait_secondaire_province.csv",
    "data/03_transformation/base_apuree",
    "data/03_transformation/dictionnaire_variables_modele.csv",
    "data/03_transformation/metadonnees/dictionnaire_bases_modele.csv",
    "data/04_analyse",
]
EXCLUS = shutil.ignore_patterns("node_modules", ".next", "__pycache__", "*.pyc", ".env", "next-env.d.ts",
                                "*.tsbuildinfo", "05_mises_a_jour")


def _forcer(fonction, chemin, _erreur):
    """Supprime aussi les fichiers en lecture seule ou brièvement verrouillés (synchronisation, cache Python)."""
    import os
    import stat
    import time
    os.chmod(chemin, stat.S_IWRITE)
    for _ in range(5):
        try:
            fonction(chemin)
            return
        except PermissionError:
            time.sleep(1)
    fonction(chemin)


def preparer() -> Path:
    # On vide le dossier sans le supprimer : il peut être ouvert dans un terminal, et le lien avec le projet
    # Railway (créé par « railway init » dans ce dossier) est conservé ailleurs, dans la configuration de l'outil.
    CIBLE.mkdir(exist_ok=True)
    for element in CIBLE.iterdir():
        if element.is_dir():
            shutil.rmtree(element, onexc=_forcer)
        else:
            _forcer(lambda c: Path(c).unlink(), element, None)
    for element in ELEMENTS:
        source, destination = RACINE / element, CIBLE / element
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, ignore=EXCLUS)
        else:
            shutil.copy2(source, destination)
    # La base apurée au format Excel n'est pas utile à l'application.
    for inutile in (CIBLE / "data/03_transformation/base_apuree").glob("*.xlsx"):
        inutile.unlink()
    shutil.copy2(ICI / "Dockerfile", CIBLE / "Dockerfile")
    (CIBLE / "railway.json").write_text(
        '{\n  "$schema": "https://railway.com/railway.schema.json",\n'
        '  "build": {"builder": "DOCKERFILE", "dockerfilePath": "Dockerfile"},\n'
        '  "deploy": {"healthcheckPath": "/", "healthcheckTimeout": 300, "restartPolicyType": "ON_FAILURE"}\n}\n',
        encoding="utf-8")
    (CIBLE / ".dockerignore").write_text("**/node_modules/\n**/.next/\n**/__pycache__/\n.env\n", encoding="utf-8")
    (CIBLE / ".gitignore").write_text(".env\nnode_modules/\n.next/\n__pycache__/\n", encoding="utf-8")
    # Fin de ligne Unix pour le script de démarrage (sinon le conteneur Linux ne peut pas l'exécuter).
    script = CIBLE / "application/demarrer.sh"
    script.write_bytes(script.read_bytes().replace(b"\r\n", b"\n"))
    taille = sum(f.stat().st_size for f in CIBLE.rglob("*") if f.is_file()) / 1e6
    print(f"Dossier prêt : {CIBLE} ({taille:.1f} Mo)")
    return CIBLE


if __name__ == "__main__":
    preparer()
