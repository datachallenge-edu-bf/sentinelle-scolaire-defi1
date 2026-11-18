"""python -m sentinelle.transformation : tables d'analyse et dépôt de l'étape 03."""

from ..depots import exporter_transformation
from . import executer_transformation


def main() -> None:
    resultat = executer_transformation()
    print(resultat["controles_transformation"].to_string(index=False))
    print(f"{len(exporter_transformation())} fichiers déposés dans depots/03_transformation.")


if __name__ == "__main__":
    main()
