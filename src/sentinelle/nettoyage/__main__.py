"""Point d'entrée en ligne de commande : python -m sentinelle.nettoyage"""

from ..depots import exporter_nettoyage
from .base import executer_nettoyage


def main() -> None:
    resultats = executer_nettoyage()
    print(resultats["meta_controles"].to_string(index=False))
    print(resultats["contours_web"][["niveau", "taille_ko", "mosaique_valide"]].to_string(index=False))
    depot = exporter_nettoyage()
    print(f"{len(depot)} fichiers déposés dans depots/02-nettoyage.")


if __name__ == "__main__":
    main()
