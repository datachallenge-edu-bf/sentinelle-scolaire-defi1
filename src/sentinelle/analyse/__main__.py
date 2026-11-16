from . import executer_exploration

if __name__ == "__main__":
    tables = executer_exploration()
    for nom in ["variance_cible_ensemble", "variance_cible_sexe"]:
        print(nom)
        print(tables[nom].to_string(index=False))
    for nom in ["variables_modele_ensemble", "variables_modele_sexe"]:
        print(nom)
        print(tables[nom].to_string(index=False))
