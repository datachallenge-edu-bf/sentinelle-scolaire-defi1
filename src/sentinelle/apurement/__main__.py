from . import executer_apurement

if __name__ == "__main__":
    tables = executer_apurement()
    print(tables["controles_apurement"].to_string(index=False))
    print(tables["controles_apurement_par_sexe"].to_string(index=False))
