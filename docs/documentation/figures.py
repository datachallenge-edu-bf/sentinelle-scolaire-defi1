"""Figures de la documentation de Sentinelle Scolaire, produites à partir des sorties réelles du projet.

Les chiffres viennent des mêmes fonctions que le tableau de bord (``application/api``) et des tables de l'étape 04,
pour que la documentation, l'application et les dépôts disent exactement la même chose.
Lancement, depuis ``docs/documentation`` : ``python figures.py`` (écrit dans ``figures/``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch  # noqa: E402

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
FIGURES = ICI / "figures"
sys.path.insert(0, str(RACINE / "src"))
sys.path.insert(0, str(RACINE / "application" / "api"))

import main as API  # noqa: E402
import rapport  # noqa: E402
import indicateurs as IND  # noqa: E402
from donnees import DONNEES_APPLI as D, fr  # noqa: E402

MODELISATION = RACINE / "data" / "04_analyse" / "modelisation"
COULEURS = {"faible": "#2a9d74", "moyen": "#cf8a1a", "élevé": "#d93a63"}
VERT, GRIS, ENCRE, VIOLET = "#1f8f5d", "#94a3b8", "#1e293b", "#7c3aed"
FILLES, GARCONS = "#d0702f", "#3b82f6"
UNE_COLONNE, DEUX_COLONNES = 3.4, 7.0

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#94a3b8", "axes.labelcolor": "#334155",
                     "xtick.color": "#475569", "ytick.color": "#475569", "axes.titlesize": 8,
                     "legend.fontsize": 6.8, "legend.frameon": False})


def lire(nom: str) -> pd.DataFrame:
    return pd.read_csv(MODELISATION / f"{nom}.csv", sep=";", encoding="utf-8-sig")


def enregistrer(fig, nom: str) -> None:
    fig.savefig(FIGURES / f"{nom}.png", dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("figure", nom)


def pourcent(x: float) -> str:
    return f"{fr(x)} %"


# 1. Parcours des données ------------------------------------------------------------------------

def parcours() -> None:
    etapes = [
        ("01 Collecte", "Base DGESS, Data Pack\n(167 fichiers), INSD,\nST-ESU, CONASUR", "engineer"),
        ("02 Nettoyage", "Référentiel à deux\ndécoupages, journal,\ncontrôles des totaux", "engineer\narchitect"),
        ("03 Transformation", "Panel province-année,\ndécoupage 2025,\nbase apurée", "engineer\narchitect"),
        ("04 Analyse", "Exploration,\n10 modèles, intervalles,\nSHAP, alerte de rupture", "analyst\nscientist"),
        ("05 Interprétation", "Tableau de bord,\nrapports, assistant,\nmise à jour annuelle", "analyst"),
    ]
    fig, ax = plt.subplots(figsize=(DEUX_COLONNES + 0.6, 1.6))
    ax.set_xlim(0, 10.2)
    ax.set_ylim(0, 2.2)
    ax.axis("off")
    for i, (titre, contenu, role) in enumerate(etapes):
        x = 0.05 + i * 2.05
        ax.add_patch(FancyBboxPatch((x, 0.35), 1.85, 1.7, boxstyle="round,pad=0.03,rounding_size=0.12",
                                    facecolor="#ecfdf5" if i < 4 else "#d1fae5", edgecolor=VERT, linewidth=1))
        ax.text(x + 0.925, 1.83, titre, ha="center", va="center", fontsize=6.9, fontweight="bold", color=ENCRE)
        ax.text(x + 0.925, 1.2, contenu, ha="center", va="center", fontsize=5.7, color="#334155", linespacing=1.25)
        ax.text(x + 0.925, 0.2, role, ha="center", va="top", fontsize=5.8, color=VIOLET, style="italic")
        if i < 4:
            ax.annotate("", xy=(x + 2.05, 1.2), xytext=(x + 1.88, 1.2),
                        arrowprops=dict(arrowstyle="-|>", color=VERT, lw=1.2))
    enregistrer(fig, "fig_parcours")


# 2. Carte des classes de risque ----------------------------------------------------------------

def carte() -> None:
    fig = rapport._carte("ensemble")
    fig.set_size_inches(UNE_COLONNE + 0.3, 2.7)
    enregistrer(fig, "fig_carte_2025_2026")


# 3. Taux national : observé puis prévu ---------------------------------------------------------

def trajectoire_nationale() -> dict:
    b = D.base.copy()
    observe = b.groupby("annee_scolaire").apply(
        lambda g: np.average(g["abandon_primaire_precedent"], weights=g["eleves_primaire"]))
    sans_rupture = b[b["evolution_eleves_primaire"].abs() <= 0.30].groupby("annee_scolaire").apply(
        lambda g: np.average(g["abandon_primaire_precedent"], weights=g["eleves_primaire"]))
    region = pd.read_csv(RACINE / "data" / "05_interpretation" / "indicateurs_cles_region.csv", sep=";",
                         encoding="utf-8-sig")
    pays = region[region["region"] == "Burkina Faso"].iloc[0]
    annees_prevues = ["2025_2026", "2026_2027", "2027_2028"]
    prevu = [float(pays[f"taux_pondere_{a}"]) for a in annees_prevues]
    abandons = [int(pays[f"abandons_estimes_{a}"]) for a in annees_prevues]

    fig, ax = plt.subplots(figsize=(UNE_COLONNE, 2.0))
    x_obs = list(observe.index)
    ax.plot(range(len(x_obs)), observe.values, color=GRIS, marker="o", ms=2.5, lw=1, label="observé, ruptures comprises")
    ax.plot(range(len(x_obs)), sans_rupture.reindex(x_obs).values, color=VERT, marker="o", ms=3, lw=1.6,
            label="observé, hors ruptures")
    xp = list(range(len(x_obs) - 1, len(x_obs) + 3))
    yp = [float(pays["taux_pondere_2024_2025"])] + prevu
    ax.plot(xp, yp, color=COULEURS["élevé"], ls="--", marker="o", ms=3, lw=1.6, label="prévu (47 provinces)")
    for k in (0, 2):
        ax.annotate(f"{fr(prevu[k])} %\n≈ {abandons[k] // 1000} 000 élèves", (xp[k + 1], prevu[k]),
                    textcoords="offset points", xytext=(0, 7), ha="center", fontsize=5.6)
    etiquettes = x_obs + ["2025-2026", "2026-2027", "2027-2028"]
    ax.set_xticks(range(len(etiquettes)), [e[2:4] + "-\n" + e[7:] for e in etiquettes], fontsize=5.6)
    ax.set_ylabel("Taux d'abandon (%)")
    ax.set_ylim(0, max(observe.max(), max(prevu)) * 1.3)
    ax.grid(axis="y", color="#e2e8f0", lw=0.6)
    ax.legend(loc="upper left", fontsize=5.8)
    enregistrer(fig, "fig_trajectoire_nationale")
    return {"prevu": prevu, "abandons": abandons, "observe_2024": float(pays["taux_pondere_2024_2025"])}


# 4. Classes de risque d'une année à l'autre -----------------------------------------------------

def classes_par_annee() -> None:
    n = API.national("ensemble")
    annees = n["annees"]
    fig, ax = plt.subplots(figsize=(UNE_COLONNE, 1.7))
    bas = np.zeros(len(annees))
    for c in ["faible", "moyen", "élevé"]:
        v = np.array([sum(p["serie"][k]["classe"] == c for p in n["provinces"]) for k in range(len(annees))])
        ax.bar(range(len(annees)), v, bottom=bas, color=COULEURS[c], width=0.6, label=c.capitalize())
        for i, (b, h) in enumerate(zip(bas, v)):
            if h:
                ax.text(i, b + h / 2, str(h), ha="center", va="center", color="white", fontsize=6.5, fontweight="bold")
        bas += v
    ax.set_xticks(range(len(annees)), [a + ("\nobservé" if i == 0 else "\nprévu") for i, a in enumerate(annees)], fontsize=6)
    ax.set_ylabel("Provinces")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    enregistrer(fig, "fig_classes_par_annee")


# 5. Trajectoire d'une province : retour amorti -------------------------------------------------

def trajectoire_province(pcode: str = "BF5401") -> None:
    p = API.province(pcode, "ensemble")
    fig = rapport._historique(p)
    fig.set_size_inches(UNE_COLONNE, 1.9)
    fig.axes[0].set_title(f"{p['identite']['province']} : taux observé, prévision et intervalle à 80 %", loc="left")
    enregistrer(fig, "fig_trajectoire_loroum")


# 6. Fiabilité : erreur des dix modèles ---------------------------------------------------------

NOMS = {"reference_annee_precedente": "Taux de l'année précédente", "reference_niveau_habituel": "Niveau habituel",
        "reference_niveau_retreci": "Niveau rétréci (région)", "elastic_net": "Elastic net",
        "ridge_effet_province": "Ridge, effet province", "lightgbm": "LightGBM",
        "lightgbm_elimination": "LightGBM, élimination SHAP", "moyenne_elastic_lightgbm": "Moyenne elastic + LightGBM",
        "retour_amorti": "Retour amorti (retenu)", "combinaison_niveau_elastic": "Niveau habituel + elastic"}


def comparaison_modeles() -> pd.DataFrame:
    s = lire("synthese_modeles_ensemble")
    s1 = s[s["horizon"] == 1].pivot_table(index="modele", columns="role", values="erreur_absolue_moyenne")
    s1 = s1.sort_values("sélection", ascending=False)
    fig, ax = plt.subplots(figsize=(UNE_COLONNE, 2.4))
    y = np.arange(len(s1))
    ax.barh(y + 0.19, s1["sélection"], height=0.36, color="#cbd5e1", label="plis de sélection (choix)")
    ax.barh(y - 0.19, s1["test final"], height=0.36,
            color=[VERT if m == "retour_amorti" else "#64748b" for m in s1.index], label="test final 2024-2025")
    for i, v in enumerate(s1["test final"]):
        ax.text(v + 0.1, i - 0.19, fr(v, 2), va="center", fontsize=5.6)
    ax.set_yticks(y, [NOMS.get(m, m) for m in s1.index], fontsize=6.2)
    ax.set_xlabel("Erreur absolue moyenne (points de taux), prévision à un an")
    ax.legend(loc="upper center", bbox_to_anchor=(0.4, 1.12), ncol=2, fontsize=5.8)
    ax.grid(axis="x", color="#e2e8f0", lw=0.6)
    enregistrer(fig, "fig_comparaison_modeles")
    return s


def couverture() -> pd.DataFrame:
    i = lire("intervalle_ensemble")
    j = lire("intervalle_sexe")
    fig, ax = plt.subplots(figsize=(UNE_COLONNE, 1.45))
    h = np.arange(1, 4)
    ax.bar(h - 0.18, i["couverture_test_final"] * 100, width=0.34, color=VERT, label="ensemble")
    ax.bar(h + 0.18, j["couverture_test_final"] * 100, width=0.34, color="#86efac", label="par sexe")
    ax.axhline(80, color=COULEURS["élevé"], lw=1, ls="--")
    ax.text(3.45, 81, "cible 80 %", fontsize=5.8, color=COULEURS["élevé"], ha="right", va="bottom")
    for k in range(3):
        ax.text(h[k] - 0.18, i["couverture_test_final"].iloc[k] * 100 + 1, f"{i['couverture_test_final'].iloc[k] * 100:.0f}",
                ha="center", fontsize=5.6)
        ax.text(h[k] + 0.18, j["couverture_test_final"].iloc[k] * 100 + 1, f"{j['couverture_test_final'].iloc[k] * 100:.0f}",
                ha="center", fontsize=5.6)
    ax.set_xticks(h, ["1 an", "2 ans", "3 ans"])
    ax.set_ylim(0, 105)
    ax.set_ylabel("Couverture au test (%)")
    ax.legend(loc="lower right", ncol=2)
    enregistrer(fig, "fig_couverture")
    return i


# 7. Explication : valeurs SHAP -------------------------------------------------------------------

def beeswarm() -> None:
    import shap
    c = lire("explication_contributions_ensemble").set_index("province_pcode")
    v = lire("explication_valeurs_ensemble").set_index("province_pcode")[c.columns]
    ordre = c.abs().mean().sort_values(ascending=False).index
    plt.figure()
    shap.summary_plot(c[ordre].values, v[ordre], feature_names=[IND.libelle(x) if x in IND.valeurs().columns
                                                                 else x for x in ordre],
                      show=False, plot_size=(UNE_COLONNE + 0.6, 2.6), color_bar_label="Valeur de la variable")
    fig = plt.gcf()
    for ax in fig.axes:
        ax.tick_params(labelsize=6.3)
        ax.xaxis.label.set_size(6.8)
    fig.axes[0].set_xlabel("Valeur SHAP (points de taux d'abandon)")
    barre = fig.axes[-1]
    barre.set_yticklabels(["Faible", "Élevée"])
    barre.set_ylabel("Valeur de la variable", fontsize=6.5)
    barre.tick_params(labelsize=6)
    enregistrer(fig, "fig_shap")


# 8. Provinces qui résistent ----------------------------------------------------------------------

def resistantes() -> list[dict]:
    r = API._resistantes("ensemble", n=6)
    fig, ax = plt.subplots(figsize=(UNE_COLONNE, 1.55))
    for i, x in enumerate(r):
        ax.plot([x["observe"], x["attendu"]], [i, i], color="#cbd5e1", lw=2.2, zorder=1)
        ax.scatter(x["attendu"], i, color=GRIS, s=22, zorder=2)
        ax.scatter(x["observe"], i, color=VERT, s=22, zorder=3)
        ax.text(x["observe"] - 0.6, i, f"−{fr(abs(x['ecart']))}", ha="right", va="center", fontsize=5.8, color=VERT)
    ax.set_yticks(range(len(r)), [x["province"] for x in r], fontsize=6.3)
    ax.invert_yaxis()
    ax.set_xlabel("Niveau habituel d'abandon (%)")
    ax.legend(handles=[Patch(color=VERT, label="observé"), Patch(color=GRIS, label="attendu (province non vue)")],
              loc="lower right")
    enregistrer(fig, "fig_resistantes")
    return r


# 9. Filles et garçons ------------------------------------------------------------------------------

def filles_garcons() -> None:
    n = API.national("ensemble")
    s = pd.DataFrame(n["sexe_par_region"][1]).sort_values("garcons", ascending=False)
    fig, ax = plt.subplots(figsize=(DEUX_COLONNES * 0.5, 1.6))
    x = np.arange(len(s))
    ax.bar(x - 0.2, s["filles"], width=0.4, color=FILLES, label="filles")
    ax.bar(x + 0.2, s["garcons"], width=0.4, color=GARCONS, label="garçons")
    ax.set_xticks(x, s["region"], rotation=55, ha="right", fontsize=5.8)
    ax.set_ylabel("Taux prévu 2025-2026 (%)")
    ax.legend(ncol=2, loc="upper right")
    ax.grid(axis="y", color="#e2e8f0", lw=0.6)
    enregistrer(fig, "fig_filles_garcons")


# 10. Indicateurs liés au risque ------------------------------------------------------------------

def liens_indicateurs() -> pd.DataFrame:
    lignes = []
    for v in IND.valeurs().columns:
        if v in ("abandon_primaire_precedent", "promotion_primaire_precedente", "eleves_primaire",
                 "evolution_eleves_primaire"):
            continue
        r = IND.lien_avec_risque(v)
        if r is not None:
            lignes.append({"variable": v, "libelle": IND.libelle(v), "r": r})
    t = pd.DataFrame(lignes).sort_values("r", key=abs, ascending=False).head(12).sort_values("r")
    fig, ax = plt.subplots(figsize=(UNE_COLONNE, 2.3))
    ax.barh(range(len(t)), t["r"], color=[COULEURS["élevé"] if r > 0 else COULEURS["faible"] for r in t["r"]], height=0.6)
    ax.set_yticks(range(len(t)), [l[:46] for l in t["libelle"]], fontsize=5.9)
    ax.axvline(0, color="#64748b", lw=0.8)
    ax.set_xlabel("Corrélation de rang avec le taux prévu (47 provinces)")
    ax.grid(axis="x", color="#e2e8f0", lw=0.6)
    enregistrer(fig, "fig_liens_indicateurs")
    return t


# 11. Alerte de rupture ---------------------------------------------------------------------------

def alerte() -> pd.DataFrame:
    e = lire("evaluation_alerte_rupture")
    fig, ax = plt.subplots(figsize=(UNE_COLONNE * 0.5, 1.45))
    ax.bar(range(len(e)), e["auc"], color=[VIOLET if r == "test final" else "#c4b5fd" for r in e["role"]], width=0.6)
    for i, v in enumerate(e["auc"]):
        ax.text(i, v + 0.01, fr(v, 2), ha="center", fontsize=5.6)
    ax.set_xticks(range(len(e)), [a[2:4] + "-" + a[7:] for a in e["annee_cible"]], fontsize=6)
    ax.set_ylim(0.5, 1.02)
    ax.set_ylabel("AUC")
    enregistrer(fig, "fig_alerte_auc")
    return e



# 12. Architecture de l'application ---------------------------------------------------------------

def architecture() -> None:
    fig, ax = plt.subplots(figsize=(UNE_COLONNE + 0.2, 2.45))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7.4)
    ax.axis("off")

    def boite(x, y, l, h, titre, texte, fond):
        ax.add_patch(FancyBboxPatch((x, y), l, h, boxstyle="round,pad=0.04,rounding_size=0.15",
                                    facecolor=fond, edgecolor="#475569", linewidth=0.8))
        ax.text(x + l / 2, y + h - 0.32, titre, ha="center", va="top", fontsize=6.6, fontweight="bold", color=ENCRE)
        ax.text(x + l / 2, y + h / 2 - 0.25, texte, ha="center", va="center", fontsize=5.4, color="#334155", linespacing=1.2)

    boite(0.2, 5.0, 9.6, 2.2, "Navigateur du décideur", "Site Next.js (React) : carte MapLibre GL sans tuiles externes,\n"
          "graphiques ECharts, tiroir d'alertes, assistant, simulateur", "#e0f2fe")
    boite(0.2, 2.25, 9.6, 2.3, "API FastAPI", "carte, vue nationale sur 4 ans, fiches, régions, simulateur,\n"
          "rapports PDF (reportlab), mise à jour annuelle, assistant (Gemini ou hors ligne)", "#ecfdf5")
    boite(0.2, 0.1, 4.6, 1.75, "Sorties de l'analyse", "prévisions, SHAP, alerte,\nindicateurs (CSV)", "#f8fafc")
    boite(5.2, 0.1, 4.6, 1.75, "Modèles sauvegardés", "LightGBM, elastic net,\nalerte, fiche du modèle", "#f8fafc")
    for x in (2.5, 7.5):
        ax.annotate("", xy=(x, 2.25), xytext=(x, 1.85), arrowprops=dict(arrowstyle="-|>", color="#475569", lw=0.9))
    ax.annotate("", xy=(5, 5.0), xytext=(5, 4.55), arrowprops=dict(arrowstyle="<|-|>", color="#475569", lw=0.9))
    ax.text(5.15, 4.78, "JSON, PDF", fontsize=5.2, color="#475569", va="center")
    enregistrer(fig, "fig_architecture")


# 13. Erreur selon l'horizon ----------------------------------------------------------------------

def erreur_horizon() -> None:
    s = lire("synthese_modeles_ensemble")
    t = s[s["role"] == "test final"].pivot_table(index="horizon", columns="modele", values="erreur_absolue_moyenne")
    fig, ax = plt.subplots(figsize=(UNE_COLONNE, 1.6))
    for m, c, w in [("reference_annee_precedente", "#94a3b8", 1), ("lightgbm", "#cf8a1a", 1),
                    ("reference_niveau_habituel", "#3b82f6", 1.2), ("retour_amorti", VERT, 2)]:
        ax.plot(t.index, t[m], marker="o", ms=3.5, color=c, lw=w, label=NOMS[m])
    ax.set_xticks([1, 2, 3], ["1 an", "2 ans", "3 ans"])
    ax.set_ylabel("Erreur au test (points)")
    ax.set_yscale("log")
    ax.set_yticks([3, 4, 6, 10, 15], ["3", "4", "6", "10", "15"])
    ax.legend(fontsize=5.6, loc="upper left", ncol=2)
    ax.grid(axis="y", color="#e2e8f0", lw=0.6)
    enregistrer(fig, "fig_erreur_horizon")


# 14. Signaux de l'alerte de rupture --------------------------------------------------------------

def signaux_alerte() -> None:
    c = lire("coefficients_alerte_rupture").sort_values("coefficient_standardise")
    fig, ax = plt.subplots(figsize=(UNE_COLONNE * 0.5 + 0.4, 1.45))
    ax.barh(range(len(c)), c["coefficient_standardise"],
            color=[VIOLET if v > 0 else "#c4b5fd" for v in c["coefficient_standardise"]], height=0.6)
    ax.set_yticks(range(len(c)), c["libelle"], fontsize=5.6)
    ax.axvline(0, color="#64748b", lw=0.7)
    ax.set_xlabel("Coefficient standardisé", fontsize=6)
    enregistrer(fig, "fig_signaux_alerte")


# 15. Décisions sur les variables -----------------------------------------------------------------

def decisions_variables() -> None:
    d = pd.read_csv(RACINE / "data" / "04_analyse" / "exploration" / "decision_variables_ensemble.csv", sep=";",
                    encoding="utf-8-sig")

    def famille(m: str) -> str:
        m = str(m)
        if m.startswith("candidate"):
            return "gardée pour les modèles"
        if m.startswith("colinéaire"):
            return "colinéaire (|ρ| ≥ 0,85)"
        if m.startswith("VIF"):
            return "redondante (VIF > 10)"
        if m.startswith("lien faible"):
            return "lien faible et instable"
        if m.startswith("trop estimée"):
            return "trop peu observée"
        return "identité comptable ou technique"

    t = d["motif"].map(famille).value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(UNE_COLONNE * 0.5 + 0.4, 1.45))
    ax.barh(range(len(t)), t.values, color=[VERT if "gardée" in i else "#cbd5e1" for i in t.index], height=0.6)
    for i, v in enumerate(t.values):
        ax.text(v + 0.4, i, str(v), va="center", fontsize=5.6)
    ax.set_yticks(range(len(t)), t.index, fontsize=5.6)
    ax.set_xlabel("Variables (sur 69)", fontsize=6)
    enregistrer(fig, "fig_decisions_variables")


# 16. Cartes des quatre années et des filles et garçons ------------------------------------------

def _carte_axe(ax, population: str, k: int, titre: str) -> None:
    n = API.national(population)
    serie = {q["pcode"]: q for q in n["provinces"]}
    g = D.provinces.copy()
    g["classe"] = g["province_pcode"].map(lambda c: serie[c]["serie"][k]["classe"] if c in serie else None)
    g.plot(ax=ax, color=g["classe"].map(COULEURS).fillna("#cbd5e1"), edgecolor="white", linewidth=0.35)
    if k >= 1:
        r = g[g["province_pcode"].map(lambda c: serie.get(c, {}).get("rupture") == "élevé")]
        r.plot(ax=ax, facecolor="none", edgecolor="#1e293b", hatch="//////", linewidth=0)
    D.regions.boundary.plot(ax=ax, color="#334155", linewidth=0.5)
    comptes = {c: int((g["classe"] == c).sum()) for c in COULEURS}
    ax.set_title(f"{titre}\n{comptes['élevé']} élevé · {comptes['moyen']} moyen · {comptes['faible']} faible", fontsize=6.4)
    ax.set_axis_off()


def cartes_annees() -> None:
    n = API.national("ensemble")
    fig, axes = plt.subplots(1, 4, figsize=(DEUX_COLONNES, 1.75))
    for k, ax in enumerate(axes):
        _carte_axe(ax, "ensemble", k, n["annees"][k] + (" (observé)" if k == 0 else " (prévu)"))
    fig.legend(handles=[Patch(color=COULEURS[c], label=c.capitalize()) for c in ["faible", "moyen", "élevé"]]
               + [Patch(facecolor="white", edgecolor="#1e293b", hatch="//////", label="Alerte de rupture")],
               loc="lower center", ncol=4, fontsize=6, bbox_to_anchor=(0.5, -0.06))
    enregistrer(fig, "fig_cartes_annees")


def cartes_sexe() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(UNE_COLONNE, 1.55))
    _carte_axe(axes[0], "F", 1, "Filles, 2025-2026")
    _carte_axe(axes[1], "G", 1, "Garçons, 2025-2026")
    enregistrer(fig, "fig_cartes_sexe")


# 17. Cycle annuel d'utilisation ------------------------------------------------------------------

def cycle_annuel() -> None:
    etapes = [("Annuaire DGESS", "taux d'abandon et\neffectifs de l'année"),
              ("Mise à jour", "import CSV ou saisie,\ncontrôles, 5 minutes"),
              ("Prévisions", "3 années suivantes,\nclasses, alertes"),
              ("Rapports", "national, 17 régions,\n47 fiches provinciales"),
              ("Actions", "ciblage, continuité\néducative, leviers"),
              ("Suivi", "indicateurs, écart\nprévu / observé")]
    fig, ax = plt.subplots(figsize=(DEUX_COLONNES + 0.8, 1.15))
    ax.set_xlim(-0.05, 12.05)
    ax.set_ylim(-0.75, 1.9)
    ax.axis("off")
    for i, (titre, texte) in enumerate(etapes):
        x = 0.05 + i * 2
        ax.add_patch(FancyBboxPatch((x, 0.2), 1.82, 1.55, boxstyle="round,pad=0.03,rounding_size=0.12",
                                    facecolor="#ecfdf5" if i % 2 == 0 else "#f0f9ff", edgecolor=VERT, linewidth=0.9))
        ax.text(x + 0.91, 1.45, titre, ha="center", va="center", fontsize=5.9, fontweight="bold", color=ENCRE)
        ax.text(x + 0.91, 0.78, texte, ha="center", va="center", fontsize=5.0, color="#334155", linespacing=1.2)
        if i < len(etapes) - 1:
            ax.annotate("", xy=(x + 2.02, 0.98), xytext=(x + 1.87, 0.98),
                        arrowprops=dict(arrowstyle="-|>", color=VERT, lw=1.1))
    ax.annotate("", xy=(0.9, 0.18), xytext=(11.0, 0.18),
                arrowprops=dict(arrowstyle="-|>", color="#94a3b8", lw=0.9, connectionstyle="arc3,rad=-0.06"))
    ax.text(6, -0.66, "l'année suivante, le cycle recommence ; réentraînement complet tous les deux ou trois ans",
            ha="center", fontsize=5.6, color="#475569", style="italic")
    enregistrer(fig, "fig_cycle_annuel")


if __name__ == "__main__":
    FIGURES.mkdir(exist_ok=True)
    parcours()
    carte()
    national = trajectoire_nationale()
    classes_par_annee()
    trajectoire_province()
    comparaison_modeles()
    couverture()
    beeswarm()
    r = resistantes()
    filles_garcons()
    t = liens_indicateurs()
    alerte()
    architecture()
    erreur_horizon()
    signaux_alerte()
    decisions_variables()
    cartes_annees()
    cartes_sexe()
    cycle_annuel()
    print("national", national)
    print("liens", t[["libelle", "r"]].to_string(index=False))
