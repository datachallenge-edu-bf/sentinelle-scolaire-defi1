"""Point d'entrée en ligne de commande : python -m sentinelle.collecte"""

from ..depots import exporter_collecte
from .extraction import executer_collecte


def main() -> None:
    resultats = executer_collecte()
    registre = resultats["registre"]
    alertes = resultats["couverture"].query("alerte != ''")
    print(f"{registre['jeu'].nunique()} jeux, {len(registre)} fichiers sources, "
          f"{registre['nb_lignes'].astype(int).sum()} lignes extraites.")
    if not alertes.empty:
        print("Alertes de couverture :")
        print(alertes.to_string(index=False))
    depot = exporter_collecte()
    print(f"{len(depot)} fichiers déposés dans depots/01-collecte.")


if __name__ == "__main__":
    main()
