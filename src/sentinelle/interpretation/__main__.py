"""Étape 05 : indicateurs clés, carte d'alerte, rapports PDF, guide et code du tableau de bord, puis dépôt."""

from ..depots import exporter_interpretation
from . import executer

if __name__ == "__main__":
    resultat = executer()
    print(f"Interprétation : {resultat['provinces']} provinces, {resultat['regions']} régions, "
          f"{resultat['provinces']} fiches et {resultat['regions']} rapports régionaux.")
    print(f"{len(exporter_interpretation())} fichiers déposés dans depots/05-interpretation.")
