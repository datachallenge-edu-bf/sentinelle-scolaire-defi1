"""Classeur de la base apurée : base colorée selon le statut des cellules, rapport, journal et contrôles."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .etat import COMPLETEE, IMPUTEE, SOURCE_INSD, Apurement
from .selection import VARIABLES

COULEURS = {IMPUTEE: "FFF2A8", SOURCE_INSD: "00B050", COMPLETEE: "F4B183"}
ENTETE = PatternFill("solid", fgColor="1F3A5F")

LISEZ_MOI = [
    ("Base apurée du défi 1 : panel provincial de 2025 sans cellule vide", "titre"),
    ("Entrée : panel_province_2025 de l'étape 03 (47 provinces du découpage de 2025 × 9 années scolaires, "
     "2016-2017 à 2024-2025). La base garde 10 identifiants et 69 variables ; les colonnes retirées et leur "
     "motif sont dans la feuille « Variables retirées ».", ""),
    ("", ""),
    ("Couleurs de la feuille base_apuree", "intertitre"),
    ("Blanc : valeur observée, identique au panel de l'étape 03.", ""),
    ("Vert : valeur publiée par l'INSD (annuaires statistiques régionaux 2024), retenue après contrôle contre le panel.", ""),
    ("Jaune : valeur imputée aux étapes 1 et 2, méthode choisie par test.", ""),
    ("Orange : valeur complétée à l'étape 3 (déduite, reconstituée ou modélisée).", ""),
    ("", ""),
    ("Principes, par ordre de préférence", "intertitre"),
    ("1. Une donnée publiée ou observée passe avant toute estimation : annuaires INSD pour le post-primaire, somme "
     "des communes pour les effectifs des provinces scindées.", ""),
    ("2. Une relation exacte vérifiée sur les lignes observées passe avant un modèle : promotion = 100 − abandon − "
     "redoublement ; écart d'achèvement = achèvement du primaire − TBA en 6e ; choc = |évolution| > 30 %.", ""),
    ("3. Sinon, la méthode est choisie par test : des valeurs connues de même nature (début, fin ou milieu de série) "
     "sont masquées puis estimées par chaque méthode, et la plus précise est retenue. L'erreur est l'écart absolu "
     "moyen rapporté à l'écart typique de la variable (1 = pas mieux qu'une valeur centrale).", ""),
    ("4. Aucune valeur imputée ne sort de la plage observée de la variable (ou de la province) ; les proportions "
     "restent dans [0 ; 1].", ""),
    ("5. Part de manquants hors provinces scindées : jusqu'à 40 %, imputation complète à l'étape 1 ; de 40 à 50 %, "
     "trous intérieurs seulement ; au-delà, l'étape 1 n'impute pas et la variable passe aux étapes 2 et 3.", ""),
    ("", ""),
    ("Limites à connaître avant l'analyse", "intertitre"),
    ("• La cible (abandon de t à t+1) est la valeur abandon_primaire_precedent de l'année t+1. Seules les cibles "
     "observées (statut « observée » dans statut_cellules) servent à entraîner et à évaluer un modèle.", ""),
    ("• Les imputations utilisent des années postérieures (interpolation, report de l'année suivante, moyenne de "
     "la province) : la base convient à la description ; un modèle validé dans le temps doit imputer ses variables "
     "avec le seul passé.", ""),
    ("• Les 4 provinces scindées (Djelgodji, Karo-Peli, Dyamongou, Gobnangou) n'ont pas de série propre ; Karo-Peli "
     "n'a aucune donnée communale : ses effectifs sont estimés par TBS × enfants de 6 à 11 ans × calage.", ""),
    ("• Komandjari 2022-2023 n'a aucun élève (écoles fermées) : ses indicateurs sont des valeurs contrefactuelles.", ""),
    ("• Abandon du post-primaire et redoublement en 3e : erreur de test proche de 1 ou plus ; à utiliser en analyse "
     "de sensibilité.", ""),
    ("• 2024-2025 : aucune source publiée pour le post-primaire ; les valeurs sont des projections.", ""),
]


def _cellule(v):
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if np.isnan(v) else float(v)
    if v is not None and not isinstance(v, (int, float, str, bool)):
        return str(v)
    return v


def _feuille(classeur: Workbook, nom: str, table: pd.DataFrame, largeurs: dict | None = None, figer: str = "A2"):
    f = classeur.create_sheet(nom)
    for j, colonne in enumerate(table.columns, 1):
        c = f.cell(1, j, colonne)
        c.font, c.fill = Font(bold=True, color="FFFFFF"), ENTETE
        c.alignment = Alignment(wrap_text=True, vertical="center")
        f.column_dimensions[get_column_letter(j)].width = (largeurs or {}).get(colonne, 18)
    for i, rang in enumerate(table.itertuples(index=False), 2):
        for j, v in enumerate(rang, 1):
            f.cell(i, j, _cellule(v))
    f.freeze_panes = figer
    f.auto_filter.ref = f.dimensions
    return f


def _rapport(etat: Apurement, e1, e2, e3, journal: pd.DataFrame) -> pd.DataFrame:
    avant = e1.avant
    lignes = []
    for variable in VARIABLES:
        manquants = int(avant[variable].isna().sum())
        if manquants == 0:
            continue
        sous = journal[(journal["variable"] == variable) & (journal["nature"] != "recodage")]
        appliquees = "; ".join(f"étape {e} : {m} ({n})" for (e, m), n in sous.groupby(["etape", "methode"]).size().items())
        tests = []
        for r in e1.rapport.get(variable, {}).get("types", []):
            if r["methode"] and r["permis"]:
                tests.append(f"étape 1, {r['type']} ({r['n']}) : " + " ; ".join(
                    f"{m} {v:.2f}" for m, v in sorted(r["candidats"].items(), key=lambda t: t[1])))
        if variable in e2.tests_2024:
            tests.append("étape 2, 2024-2025 : " + " ; ".join(
                f"{m} {v:.3f}" for m, v in sorted(e2.tests_2024[variable][1].items(), key=lambda t: t[1])))
        for type_trou, (meilleure, scores) in e3.tests.get(variable, {}).items():
            tests.append(f"étape 3, {type_trou} : " + " ; ".join(
                f"{m} {v:.2f}" for m, v in sorted(scores.items(), key=lambda t: t[1])))
        lignes.append({"variable": variable, "valeurs_manquantes": manquants,
                       "part_de_la_base": round(manquants / len(avant), 3),
                       "valeurs_recodees_avant": int(((journal["variable"] == variable)
                                                      & (journal["nature"] == "recodage")).sum()),
                       "methodes_appliquees": appliquees, "methodes_testees_et_erreur": " || ".join(tests),
                       "regle": e1.rapport.get(variable, {}).get("regle", "")})
    return pd.DataFrame(lignes)


def _a_controler(etat: Apurement, e3) -> pd.DataFrame:
    d = etat.base
    lignes = []
    for c in ["abandon_primaire_precedent", "redoublement_primaire_precedent", "promotion_primaire_precedente"]:
        for i in d.index[(d[c] < 0) | (d[c] > 100)]:
            lignes.append((d.at[i, "province_nom"], d.at[i, "annee_scolaire"], c, float(d.at[i, c]),
                           "taux hors de [0 ; 100] (arrivées ou départs nets d'élèves), non corrigé"))
    lignes.append(("Karo-Peli", "2016-2017 à 2024-2025", "eleves_primaire", None,
                   f"aucune donnée communale : effectifs = TBS × enfants 6-11 × {e3.calage:.3f} ; incertitude élevée"))
    for p in ["Djelgodji", "Dyamongou", "Gobnangou"]:
        lignes.append((p, "2016-2017 à 2023-2024", "eleves_primaire", None,
                       "somme des communes ; chutes brutales liées aux fermetures d'écoles, à confirmer"))
    lignes.append(("Komandjari", "2022-2023 et 2023-2024", "plusieurs variables", None,
                   "aucun élève en 2022-2023 : indicateurs non définis, valeurs contrefactuelles ; à exclure ou à "
                   "traiter en analyse de sensibilité"))
    return pd.DataFrame(lignes, columns=["province", "annee", "variable", "valeur", "anomalie"])


def ecrire(etat: Apurement, e1, e2, e3, tables: dict[str, pd.DataFrame], chemin: Path) -> None:
    journal = tables["journal_apurement"]
    classeur = Workbook()
    f = classeur.active
    f.title = "Lisez-moi"
    for i, (texte, style) in enumerate(LISEZ_MOI, 1):
        c = f.cell(i, 1, texte)
        c.font = Font(bold=bool(style), size=13 if style == "titre" else 11)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    f.column_dimensions["A"].width = 150
    base = tables["base_apuree"]
    feuille = _feuille(classeur, "base_apuree", base, {c: 20 for c in base.columns}, figer="C2")
    colonne = {c: j for j, c in enumerate(base.columns, 1)}
    position = {i: k for k, i in enumerate(base.index)}
    for (i, variable), statut in etat.statut.items():
        if statut in COULEURS:
            feuille.cell(position[i] + 2, colonne[variable]).fill = PatternFill("solid", fgColor=COULEURS[statut])
    _feuille(classeur, "Rapport par variable", _rapport(etat, e1, e2, e3, journal),
             {"variable": 44, "methodes_appliquees": 70, "methodes_testees_et_erreur": 90, "regle": 50}, figer="B2")
    synthese = journal[journal["nature"] != "recodage"].groupby(["etape", "methode"]).agg(
        valeurs=("variable", "size"), variables=("variable", "nunique")).reset_index()
    _feuille(classeur, "Synthèse des méthodes", synthese, {"methode": 60})
    _feuille(classeur, "Journal", journal, {"variable": 44, "methode": 50, "detail": 80})
    _feuille(classeur, "Valeurs sourcées INSD", tables["sources_insd_retenues"], {"document": 60, "lien": 80})
    _feuille(classeur, "Sources rejetées", tables["sources_insd_rejetees"], {"document": 60, "lien": 80})
    _feuille(classeur, "Contrôle sources vs panel", tables["sources_insd_controle"], {"variable": 40})
    _feuille(classeur, "Valeurs à contrôler", _a_controler(etat, e3), {"anomalie": 100})
    _feuille(classeur, "Variables retirées", tables["variables_retirees"], {"variable": 50, "motif": 80})
    _feuille(classeur, "Contrôles", tables["controles_apurement"], {"controle": 40, "detail": 110})
    classeur.save(chemin)
