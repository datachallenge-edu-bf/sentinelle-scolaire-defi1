"""Étape 04 : analyse exploratoire, modèle du décrochage, puis dépôt."""

from ..depots import exporter_analyse
from . import executer_exploration, executer_modelisation

if __name__ == "__main__":
    executer_exploration()
    tables = executer_modelisation()
    print(tables["synthese_modeles_ensemble"].query("horizon == 1").to_string(index=False))
    print(f"{len(exporter_analyse())} fichiers déposés dans depots/04_analyse.")
