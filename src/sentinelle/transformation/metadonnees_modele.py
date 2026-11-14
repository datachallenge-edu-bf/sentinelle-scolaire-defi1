"""Métadonnées des bases du modèle : dictionnaire CSV, Data Package JSON et page HTML.

Le dictionnaire est reconstruit à chaque exécution à partir des tables réellement
produites, si bien que les plages, les valeurs manquantes et les années couvertes
restent exactes. Le JSON suit la spécification Frictionless Data Package (Table
Schema) : chaque table y est une ressource, avec son schéma, sa clé primaire et ses
clés étrangères.
"""

from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

import pandas as pd

from .. import config
from .fiche import DESCRIPTIONS_MENSUEL, FICHES, LIENS, TABLES

MAX_MODALITES = 12


def _type(serie: pd.Series) -> tuple[str, str]:
    """Type lisible et type Frictionless."""
    if pd.api.types.is_bool_dtype(serie):
        return "booléen", "boolean"
    if pd.api.types.is_integer_dtype(serie):
        return "entier", "integer"
    if pd.api.types.is_numeric_dtype(serie):
        valeurs = serie.dropna()
        if len(valeurs) and (valeurs == valeurs.round()).all():
            return "entier", "integer"
        return "décimal", "number"
    if serie.dropna().astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all() and serie.notna().any():
        return "date", "date"
    return "texte", "string"


def _format(valeur: float) -> str:
    if pd.isna(valeur):
        return ""
    return f"{valeur:,.0f}".replace(",", " ") if float(valeur).is_integer() else f"{valeur:,.3f}".replace(",", " ")


def _profil(serie: pd.Series, annees: pd.Series | None) -> dict:
    lisible, frictionless = _type(serie)
    valeurs = serie.dropna()
    profil = {"type": lisible, "type_frictionless": frictionless, "minimum": "", "maximum": "", "modalites": "",
              "part_manquante": round(float(serie.isna().mean()), 3), "premiere_annee": "", "derniere_annee": ""}
    if frictionless in ("integer", "number") and len(valeurs):
        profil["minimum"], profil["maximum"] = _format(valeurs.min()), _format(valeurs.max())
    elif frictionless in ("string", "boolean") and 0 < valeurs.nunique() <= MAX_MODALITES:
        profil["modalites"] = " ; ".join(sorted(map(str, valeurs.unique())))
    if annees is not None and len(valeurs):
        couvertes = annees[serie.notna()]
        profil["premiere_annee"], profil["derniere_annee"] = couvertes.min(), couvertes.max()
    return profil


def _role_description_source(table: str, variable: str, variables: dict, variables_region: dict) -> tuple[str, str, str]:
    if table in ("panel_province_annee", "panel_mensuel_province", "panel_province_2025"):
        if variable in variables:
            return variables[variable]
        if variable in DESCRIPTIONS_MENSUEL:
            return DESCRIPTIONS_MENSUEL[variable]
        return "", "", ""
    if variable in ("region_pcode", "region_nom", "methode_passage"):
        return variables[variable]
    description = variables_region.get(variable, "")
    identifiants = {"region_ancienne_pcode", "region_ancienne_nom", "annee_scolaire"}
    role = "identifiant" if variable in identifiants else "contexte"
    source = "OpenStreetMap (HOT)" if variable == "region_ancienne_nom" else (
        "COD-AB" if variable == "region_ancienne_pcode" else "DGESS, base principale")
    return role, description, source


def construire(tables: dict[str, pd.DataFrame], variables: dict, variables_region: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dictionnaire des variables et description des tables."""
    lignes = []
    for nom, table in tables.items():
        annees = table["annee_scolaire"] if "annee_scolaire" in table else (
            table["mois"] if "mois" in table else None)
        for variable in table.columns:
            libelle, unite, calcul, limites = FICHES.get(variable, ("", "", "", ""))
            role, description, source = _role_description_source(nom, variable, variables, variables_region)
            lignes.append({"table": nom, "variable": variable, "libelle": libelle, "description": description,
                           "role": role, "unite": unite, **_profil(table[variable], annees),
                           "calcul": calcul, "source": source, "limites": limites})
    dico = pd.DataFrame(lignes)

    lignes_tables = []
    for nom, table in tables.items():
        description, grain, cle, usage = TABLES[nom]
        liens = "; ".join(f"{', '.join(c)} → {cible} ({', '.join(cc)})" for t, c, cible, cc in LIENS if t == nom)
        annees = table["annee_scolaire"] if "annee_scolaire" in table else table.get("mois")
        lignes_tables.append({"table": nom, "description": description, "grain": grain, "cle": ", ".join(cle),
                              "liens": liens, "usage": usage, "lignes": len(table), "colonnes": table.shape[1],
                              "periode": f"{annees.min()} à {annees.max()}" if annees is not None else "",
                              "fichier": f"{nom}.csv", "produite_le": date.today().isoformat()})
    return dico, pd.DataFrame(lignes_tables)


def controle(dico: pd.DataFrame) -> tuple[bool, str]:
    manques = dico[(dico["libelle"] == "") | (dico["unite"] == "") | (dico["description"] == "") | (dico["source"] == "")]
    if manques.empty:
        return True, f"{len(dico)} variables de {dico['table'].nunique()} tables : libellé, description, unité et source renseignés"
    return False, "incomplètes : " + ", ".join(manques["table"] + "." + manques["variable"])


def data_package(dico: pd.DataFrame, tables_meta: pd.DataFrame) -> dict:
    """Description Frictionless Data Package des bases du modèle."""
    ressources = []
    for t in tables_meta.itertuples():
        champs = []
        for v in dico[dico["table"] == t.table].itertuples():
            champ = {"name": v.variable, "title": v.libelle, "description": v.description, "type": v.type_frictionless,
                     "unit": v.unite, "role": v.role, "source": v.source, "missing_share": v.part_manquante}
            if v.calcul:
                champ["derivation"] = v.calcul
            if v.limites:
                champ["limitations"] = v.limites
            if v.modalites:
                champ["constraints"] = {"enum": v.modalites.split(" ; ")}
            champs.append(champ)
        schema = {"fields": champs, "primaryKey": t.cle.split(", "), "missingValues": [""]}
        etrangeres = [{"fields": c, "reference": {"resource": cible, "fields": cc}}
                      for tt, c, cible, cc in LIENS if tt == t.table]
        if etrangeres:
            schema["foreignKeys"] = etrangeres
        ressources.append({"name": t.table, "path": t.fichier, "title": t.description, "description": t.usage,
                           "format": "csv", "encoding": "utf-8-sig", "dialect": {"delimiter": ";"},
                           "grain": t.grain, "rows": t.lignes, "temporal": t.periode, "schema": schema})
    return {"name": "sentinelle-scolaire-bases-modele", "title": "Sentinelle Scolaire : bases du modèle de risque de "
            "décrochage", "description": "Tables d'analyse de l'étape 03 du Data Challenge Burkina 2026, défi 1.",
            "created": date.today().isoformat(), "licenses": [{"name": "selon les conditions des données du challenge"}],
            "sources": [{"title": "DGESS, annuaires du primaire, du préscolaire et de l'éducation non formelle ; base principale"},
                        {"title": "ST-ESU, rapports mensuels"}, {"title": "SP/CONASUR, déplacés internes"},
                        {"title": "COD-AB ; OpenStreetMap (HOT)"}],
            "resources": ressources}


_STYLE = """
body{font-family:"Segoe UI",Arial,sans-serif;color:#1d1d1b;background:#fcfcfb;margin:0;padding:24px 28px;line-height:1.45}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 6px;padding-top:8px;border-top:1px solid #d8d6cf}
p.sous{color:#55534d;margin:0 0 18px}dl{display:grid;grid-template-columns:150px 1fr;gap:3px 12px;font-size:13.5px;margin:8px 0 12px}
dt{color:#55534d}dd{margin:0}table{border-collapse:collapse;width:100%;font-size:12.5px}
th{background:#eeede8;text-align:left;font-weight:600;padding:6px 7px;position:sticky;top:0}
td{padding:5px 7px;border-bottom:1px solid #e6e4de;vertical-align:top}td.code{font-family:Consolas,monospace;white-space:nowrap}
td.nombre{text-align:right;white-space:nowrap}.resume td,.resume th{font-size:13px}nav a{color:#1f5fa8;margin-right:14px}
@media print{body{padding:0}h2{page-break-before:always}th{position:static}@page{size:A4 landscape;margin:12mm}}
"""


def page_html(dico: pd.DataFrame, tables_meta: pd.DataFrame, titre: str, sous_titre: str) -> str:
    e = lambda x: html.escape(str(x)) if x == x else ""  # noqa: E731
    morceaux = [f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' "
                f"content='width=device-width,initial-scale=1'><title>{e(titre)}</title><style>{_STYLE}</style></head><body>",
                f"<h1>{e(titre)}</h1><p class='sous'>{e(sous_titre)} Produit le {date.today().isoformat()}.</p>",
                "<nav>" + "".join(f"<a href='#{e(t)}'>{e(t)}</a>" for t in tables_meta["table"]) + "</nav>",
                "<h2>Tables</h2><table class='resume'><tr><th>Table</th><th>Contenu</th><th>Une ligne par</th>"
                "<th>Clé</th><th>Lignes</th><th>Période</th></tr>"]
    for t in tables_meta.itertuples():
        morceaux.append(f"<tr><td class='code'><a href='#{e(t.table)}'>{e(t.table)}</a></td><td>{e(t.description)}</td>"
                        f"<td>{e(t.grain)}</td><td class='code'>{e(t.cle)}</td><td class='nombre'>{t.lignes}</td>"
                        f"<td>{e(t.periode)}</td></tr>")
    morceaux.append("</table>")
    for t in tables_meta.itertuples():
        morceaux.append(f"<h2 id='{e(t.table)}'>{e(t.table)}</h2><dl><dt>Contenu</dt><dd>{e(t.description)}</dd>"
                        f"<dt>Une ligne par</dt><dd>{e(t.grain)}</dd><dt>Clé</dt><dd>{e(t.cle)}</dd>"
                        f"<dt>Liens</dt><dd>{e(t.liens) or 'aucun'}</dd><dt>Usage</dt><dd>{e(t.usage)}</dd>"
                        f"<dt>Taille</dt><dd>{t.lignes} lignes, {t.colonnes} variables, {e(t.periode)}</dd>"
                        f"<dt>Fichier</dt><dd>{e(t.fichier)}</dd></dl>")
        morceaux.append("<table><tr><th>Variable</th><th>Libellé</th><th>Description</th><th>Rôle</th><th>Unité</th>"
                        "<th>Type</th><th>Valeurs</th><th>Manquantes</th><th>Années</th><th>Calcul</th>"
                        "<th>Source</th><th>Limites</th></tr>")
        for v in dico[dico["table"] == t.table].itertuples():
            valeurs = v.modalites or (f"{v.minimum} à {v.maximum}" if v.minimum != "" else "")
            annees = f"{v.premiere_annee} à {v.derniere_annee}" if v.premiere_annee else ""
            morceaux.append(f"<tr><td class='code'>{e(v.variable)}</td><td>{e(v.libelle)}</td><td>{e(v.description)}</td>"
                            f"<td>{e(v.role)}</td><td>{e(v.unite)}</td><td>{e(v.type)}</td><td>{e(valeurs)}</td>"
                            f"<td class='nombre'>{v.part_manquante:.0%}</td><td>{e(annees)}</td><td>{e(v.calcul)}</td>"
                            f"<td>{e(v.source)}</td><td>{e(v.limites)}</td></tr>")
        morceaux.append("</table>")
    morceaux.append("</body></html>")
    return "\n".join(morceaux)


def ecrire(tables: dict[str, pd.DataFrame], variables: dict, variables_region: dict, dossier: Path) -> dict:
    dossier = config.verifier_ecriture(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    dico, tables_meta = construire(tables, variables, variables_region)
    colonnes = [c for c in dico.columns if c != "type_frictionless"]
    dico[colonnes].to_csv(dossier / "dictionnaire_bases_modele.csv", sep=config.SEPARATEUR,
                          encoding=config.ENCODAGE_SORTIE, index=False)
    tables_meta.to_csv(dossier / "tables_bases_modele.csv", sep=config.SEPARATEUR,
                       encoding=config.ENCODAGE_SORTIE, index=False)
    (dossier / "datapackage.json").write_text(json.dumps(data_package(dico, tables_meta), ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    (dossier / "dictionnaire_bases_modele.html").write_text(
        page_html(dico, tables_meta, "Sentinelle Scolaire : dictionnaire des bases du modèle",
                  "Défi 1, étape 03. Tables d'analyse du risque de décrochage scolaire, une fiche par variable."),
        encoding="utf-8")
    return {"dictionnaire": dico, "tables": tables_meta, "controle": controle(dico)}
