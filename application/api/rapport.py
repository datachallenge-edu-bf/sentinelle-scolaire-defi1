"""Rapports PDF de décision (national, région, province), rédigés automatiquement à partir des données.

Chaque rapport reprend les chiffres de l'API (aucun calcul nouveau), les met en forme pour l'impression et
termine par des pistes d'action. Les pistes sont liées aux facteurs qui élèvent le niveau d'abandon : ce sont des
points de départ pour les équipes, pas des effets garantis (les facteurs décrivent des associations).
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,  # noqa: E402
                                TableStyle)

from donnees import DONNEES_APPLI as D, fr  # noqa: E402

POLICES = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("Sentinelle", str(POLICES / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("Sentinelle-Gras", str(POLICES / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("Sentinelle", normal="Sentinelle", bold="Sentinelle-Gras")
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#94a3b8", "axes.labelcolor": "#334155",
                     "xtick.color": "#475569", "ytick.color": "#475569"})

COULEURS = {"faible": "#2a9d74", "moyen": "#cf8a1a", "élevé": "#d93a63"}
VERT, ENCRE, GRIS, FOND = "#1f8f5d", "#0f172a", "#64748b", "#f1f5f9"
POPULATIONS = {"ensemble": "ensemble des élèves", "F": "filles", "G": "garçons"}

PISTES = {
    "part_cp1": "Suivre de près les élèves du CP1 (redoublements, absences, départs précoces) et renforcer l'apprentissage de la lecture dès la première année.",
    "hors_ecole_16_18_province": "Ouvrir des passerelles de seconde chance (éducation non formelle, formation professionnelle) pour les adolescents non scolarisés.",
    "ni_ecole_ni_emploi_15_24_province": "Coordonner l'école avec les programmes d'emploi et de formation des jeunes, pour que la scolarité garde une perspective.",
    "eleves_par_maitre_primaire": "Orienter les affectations d'enseignants vers les écoles aux classes les plus chargées.",
    "deficit_places_pour_100_eleves_primaire": "Combler le déficit de places assises (tables-bancs, salles de classe).",
    "parite_scolarisation_post_primaire_province": "Accompagner le maintien des filles au-delà du primaire (proximité des collèges, sécurité, sensibilisation des familles).",
    "parite_tbs_post_primaire_province": "Accompagner le maintien des filles au-delà du primaire (proximité des collèges, sécurité, sensibilisation des familles).",
    "pauvrete_province": "Cibler les appuis aux familles (cantines, kits scolaires, transferts) sur les ménages les plus pauvres.",
    "rapport_cm2_cp1": "Analyser les ruptures de parcours entre le CP1 et le CM2 école par école.",
    "achevement_post_primaire_province": "Renforcer l'offre et l'accompagnement au post-primaire pour donner un débouché au cycle primaire.",
    "abandons_primaire_orpaillage_pour_1000_region": "Sensibiliser les familles et contrôler le travail des enfants sur les sites d'orpaillage.",
    "abandons_primaire_mariage_grossesse_pour_1000_region": "Prévenir les mariages et grossesses précoces avec les leaders communautaires.",
    "part_eleves_primaire_12_ans_et_plus": "Proposer un rattrapage accéléré aux élèves âgés pour éviter leur sortie précoce.",
    "part_entrants_cp1_8_ans_et_plus": "Favoriser l'inscription au CP1 à l'âge normal (campagnes de recrutement, état civil).",
    "travail_enfants_7_14_province": "Agir contre le travail des enfants avec les services sociaux et les communautés.",
    "part_salles_primaire_murs_precaires": "Remplacer les salles en matériaux précaires.",
    "part_ecoles_primaires_cycle_incomplet": "Compléter les écoles à cycle incomplet pour éviter les ruptures en cours de primaire.",
}
PISTE_RUPTURE = ("Préparer la continuité éducative en cas de fermetures ou de déplacements : écoles d'accueil, "
                 "enseignement à distance, recensement des élèves déplacés, avec les acteurs de l'éducation en situation d'urgence.")


# Mise en forme -------------------------------------------------------------------------------------

def _styles() -> dict:
    base = dict(fontName="Sentinelle", textColor=colors.HexColor(ENCRE), alignment=TA_LEFT)
    return {
        "titre": ParagraphStyle("titre", **base, fontSize=19, leading=23, spaceAfter=2),
        "sous": ParagraphStyle("sous", **{**base, "textColor": colors.HexColor(GRIS)}, fontSize=9.5, leading=13, spaceAfter=8),
        "h2": ParagraphStyle("h2", **{**base, "textColor": colors.HexColor(VERT)}, fontSize=12.5, leading=16, spaceBefore=9, spaceAfter=4),
        "corps": ParagraphStyle("corps", **base, fontSize=9.3, leading=13.2, spaceAfter=3),
        "puce": ParagraphStyle("puce", **base, fontSize=9.3, leading=13.2, leftIndent=11, bulletIndent=2, spaceAfter=2),
        "petit": ParagraphStyle("petit", **{**base, "textColor": colors.HexColor(GRIS)}, fontSize=7.8, leading=10.5),
        "cellule": ParagraphStyle("cellule", **base, fontSize=8.3, leading=10.5),
    }


S = _styles()


def _pct(x) -> str:
    return "n.d." if x is None or (isinstance(x, float) and np.isnan(x)) else f"{fr(float(x))} %"


def _ic(bas, haut) -> str:
    return "" if bas is None else f"[{fr(bas)} ; {fr(haut)}]"


def _image(fig, largeur_mm: float) -> Image:
    tampon = BytesIO()
    fig.savefig(tampon, format="png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    tampon.seek(0)
    l, h = fig.get_size_inches()
    return Image(tampon, width=largeur_mm * mm, height=largeur_mm * mm * h / l)


def _tableau(lignes: list[list], largeurs: list[float], couleurs_classes: dict | None = None) -> Table:
    donnees = [[Paragraph(str(c), S["cellule"]) if isinstance(c, str) else c for c in l] for l in lignes]
    t = Table(donnees, colWidths=[w * mm for w in largeurs], repeatRows=1)
    style = [("FONTNAME", (0, 0), (-1, -1), "Sentinelle"), ("FONTSIZE", (0, 0), (-1, -1), 8.3),
             ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
             ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for (ligne, colonne), classe in (couleurs_classes or {}).items():
        style.append(("TEXTCOLOR", (colonne, ligne), (colonne, ligne), colors.HexColor(COULEURS.get(classe, ENCRE))))
    t.setStyle(TableStyle(style))
    return t


def _chiffres(cases: list[tuple[str, str, str]]) -> Table:
    """Bandeau de chiffres clés : (valeur, libellé, couleur)."""
    cellules = [[Paragraph(f"<font size=15><b>{v}</b></font><br/><font size=7.8 color='{GRIS}'>{l}</font>", S["corps"]) for v, l, _ in cases]]
    t = Table(cellules, colWidths=[(178 / len(cases)) * mm] * len(cases))
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
             ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(FOND))]
    for i, (_, _, c) in enumerate(cases):
        style.append(("LINEABOVE", (i, 0), (i, 0), 2.2, colors.HexColor(c)))
    t.setStyle(TableStyle(style))
    return t


def _document(titre: str):
    tampon = BytesIO()
    jour = date.today().strftime("%d/%m/%Y")

    def pied(canvas, doc):
        canvas.saveState()
        canvas.setFont("Sentinelle", 7.5)
        canvas.setFillColor(colors.HexColor(GRIS))
        canvas.drawString(16 * mm, 10 * mm, f"Sentinelle Scolaire · {titre} · produit le {jour} à partir des données 2016-2017 à 2024-2025")
        canvas.drawRightString(194 * mm, 10 * mm, f"page {doc.page}")
        canvas.setStrokeColor(colors.HexColor(VERT))
        canvas.setLineWidth(1.2)
        canvas.line(16 * mm, 287 * mm, 194 * mm, 287 * mm)
        canvas.restoreState()

    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=15 * mm,
                            bottomMargin=16 * mm, title=f"Sentinelle Scolaire · {titre}", author="Sentinelle Scolaire")
    return doc, tampon, pied


def _sources(population: str = "ensemble") -> list:
    return [KeepTogether([Paragraph("Méthode et sources", S["h2"]),
            Paragraph("Prévision : retour amorti vers le niveau habituel de chaque province (moyenne des taux d'abandon des "
                      "années sans rupture) ; l'écart de la dernière année se résorbe progressivement. Modèle choisi parmi dix "
                      "sur des années passées, sans utiliser l'année de test ; erreur moyenne au "
                      "test final de " + fr(D.erreur_test_final(population)) + " points. Intervalles conformes à 80 %, calculés en logit. Facteurs : LightGBM et valeurs "
                      "SHAP, validés sur des provinces non vues ; ce sont des associations, pas des causes. Alerte de rupture : "
                      "régression logistique sur sept signaux (AUC de 0,96 au test final).", S["petit"]),
            Spacer(1, 3),
            Paragraph("Sources : Data Pack du Data Challenge Burkina 2026 (annuaires statistiques de l'éducation, 2016-2017 à "
                      "2024-2025) ; INSD, RGPH 2019 (Mesure et cartographie de la pauvreté, 2022) et annuaires régionaux 2024 ; "
                      "contours du découpage de 2025.", S["petit"])])]


# Figures --------------------------------------------------------------------------------------------

def _carte(population: str, k: int = 1, region: str | None = None):
    from main import national
    n = national(population)
    g = D.provinces.copy()
    serie = {p["pcode"]: p for p in n["provinces"]}
    g["classe"] = g["province_pcode"].map(lambda c: serie[c]["serie"][k]["classe"] if c in serie else None)
    g["rupture"] = g["province_pcode"].map(lambda c: serie[c]["rupture"] if c in serie else None)
    if region:
        g = g[g["region_nom"] == region]
    fig, ax = plt.subplots(figsize=(6.2, 4.6) if not region else (4.2, 3.4))
    g.plot(ax=ax, color=g["classe"].map(COULEURS).fillna("#cbd5e1"), edgecolor="white", linewidth=0.6)
    r = g[g["rupture"] == "élevé"]
    if len(r):
        r.plot(ax=ax, facecolor="none", edgecolor="#1e293b", hatch="////", linewidth=0)
    regions = D.regions if not region else D.regions[D.regions["region_nom"] == region]
    regions.boundary.plot(ax=ax, color="#334155", linewidth=0.9)
    for _, x in (g if region else regions).iterrows():
        p = x.geometry.representative_point()
        ax.annotate(x["province_nom"] if region else x["region_nom"], (p.x, p.y), ha="center", va="center",
                    fontsize=6.3 if not region else 6.8, color="#0f172a", fontweight="bold")
    ax.set_axis_off()
    ax.legend(handles=[Patch(color=COULEURS[c], label=c.capitalize()) for c in ["faible", "moyen", "élevé"]]
              + [Patch(facecolor="white", edgecolor="#1e293b", hatch="////", label="Alerte de rupture")],
              loc="upper left", fontsize=6.5, frameon=False)
    return fig


def _historique(p: dict):
    h = p["historique"][p["population"]]
    proj = p["projections"]
    annees = [x["annee"] for x in h] + [x["annee"] for x in proj]
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    xs = np.arange(len(annees))
    for i, x in enumerate(h):
        if x["rupture"]:
            ax.axvspan(i - 0.45, i + 0.45, color="#ede9fe", zorder=0)
    obs = [x["taux"] if not x["rupture"] else np.nan for x in h]
    ax.plot(xs[: len(h)], obs, color=VERT, marker="o", markersize=3.5, linewidth=1.6, label="Taux observé")
    n = len(h)
    dernier = obs[-1] if not np.isnan(obs[-1]) else proj[0]["taux"]
    ax.fill_between(xs[n - 1:], [dernier] + [x["borne_basse"] for x in proj], [dernier] + [x["borne_haute"] for x in proj],
                    color=VERT, alpha=0.15, linewidth=0, label="Intervalle à 80 %")
    ax.plot(xs[n - 1:], [dernier] + [x["taux"] for x in proj], color=VERT, linestyle="--", marker="o", markersize=3.5, linewidth=1.4, label="Prévision")
    for i, x in enumerate(proj):
        ax.annotate(f"{fr(x['taux'])} %", (n + i, x["taux"]), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7)
    ax.set_xticks(xs, annees, rotation=35, ha="right", fontsize=7)
    valeurs = [v for v in obs if not np.isnan(v)] + [x["borne_haute"] for x in proj]
    ax.set_ylim(0, max(valeurs) * 1.12)
    ax.set_ylabel("Taux d'abandon (%)")
    ax.legend(fontsize=6.8, frameon=False, ncol=3, loc="upper left")
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.6)
    return fig


def _cascade(p: dict):
    c = p["cascade"]
    noms = ["Moyenne des provinces"] + [x["libelle"] for x in c["contributions"]] + ["Autres", "Niveau expliqué"]
    valeurs = [x["contribution"] for x in c["contributions"]] + [c["autres"]]
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    cumul = c["base"]
    ax.barh(0, c["base"], color="#94a3b8")
    for i, v in enumerate(valeurs, start=1):
        ax.barh(i, v, left=cumul, color=COULEURS["élevé"] if v >= 0 else COULEURS["faible"])
        ax.annotate(f"{'+' if v >= 0 else '−'}{fr(abs(v))}", (cumul + max(v, 0), i), xytext=(3, 0), textcoords="offset points", va="center", fontsize=7)
        cumul += v
    ax.barh(len(noms) - 1, c["niveau_explique"], color=VERT)
    ax.annotate(f"{fr(c['base'])} %", (c["base"], 0), xytext=(3, 0), textcoords="offset points", va="center", fontsize=7)
    ax.annotate(f"{fr(c['niveau_explique'])} %", (c["niveau_explique"], len(noms) - 1), xytext=(3, 0), textcoords="offset points", va="center", fontsize=7, fontweight="bold")
    ax.set_yticks(range(len(noms)), noms, fontsize=7.2)
    ax.invert_yaxis()
    ax.set_xlabel("Points de taux d'abandon")
    ax.grid(axis="x", color="#e2e8f0", linewidth=0.6)
    return fig


def _pistes(variables_positives: list[str], rupture: bool) -> list:
    vues, sortie = set(), []
    for v in variables_positives:
        piste = PISTES.get(v)
        if piste and piste not in vues:
            vues.add(piste)
            sortie.append(piste)
    if rupture:
        sortie.insert(0, PISTE_RUPTURE)
    return sortie[:5]


# Rapports -------------------------------------------------------------------------------------------

def rapport_national(population: str = "ensemble") -> bytes:
    from main import national
    n = national(population)
    doc, tampon, pied = _document("Rapport national")
    k = 1
    provinces = sorted(n["provinces"], key=lambda p: -(p["serie"][k]["taux"] or 0))
    classes = {c: sum(p["serie"][k]["classe"] == c for p in provinces) for c in COULEURS}
    ruptures = [p for p in provinces if p["rupture"] == "élevé"]
    poids = sum(p["poids"] or 1 for p in provinces)
    moyenne = sum((p["serie"][k]["taux"] or 0) * (p["poids"] or 1) for p in provinces) / poids
    tete = provinces[0]

    e = [Paragraph("Risque de décrochage scolaire au primaire", S["titre"]),
         Paragraph(f"Rapport national · Burkina Faso, 47 provinces · prévision 2025-2026 · {POPULATIONS[population]}", S["sous"]),
         _chiffres([(_pct(moyenne), "taux national prévu (pondéré)", VERT),
                    (f"{classes['élevé']} / 47", "provinces en risque élevé", COULEURS["élevé"]),
                    (str(len(ruptures)), "alertes de rupture", "#7c3aed"),
                    (_pct(tete["serie"][k]["taux"]), f"taux le plus élevé : {tete['province']}", COULEURS["élevé"])]),
         Paragraph("En bref", S["h2"])]
    bref = [f"<b>{classes['élevé']}</b> provinces en risque élevé (taux prévu d'au moins {fr(n['seuils']['eleve'])} %), "
            f"<b>{classes['moyen']}</b> en risque moyen et <b>{classes['faible']}</b> en risque faible pour 2025-2026.",
            f"Les plus exposées : {', '.join(p['province'] for p in provinces[:5])}.",
            f"<b>{len(ruptures)}</b> provinces risquent une rupture de scolarisation (baisse brutale des effectifs) : "
            f"{', '.join(p['province'] for p in ruptures[:8])}{'…' if len(ruptures) > 8 else ''}.",
            "Les taux prévus restent proches jusqu'en 2027-2028 ; l'incertitude s'élargit avec l'horizon."]
    e += [Paragraph(t, S["puce"], bulletText="•") for t in bref]
    e += [Paragraph("Carte des classes de risque, 2025-2026", S["h2"]), _image(_carte(population), 150)]

    lignes = [["Rang", "Province", "Région", "Observé 2024-2025", "Prévu 2025-2026", "Intervalle à 80 %", "Classe", "Rupture"]]
    couleurs = {}
    for i, p in enumerate(provinces[:15], start=1):
        s0, s1 = p["serie"][0], p["serie"][k]
        lignes.append([str(i), p["province"], p["region"], _pct(s0["taux"]), _pct(s1["taux"]), _ic(s1["bas"], s1["haut"]), s1["classe"], p["rupture"]])
        couleurs[(i, 6)] = s1["classe"]
        couleurs[(i, 7)] = p["rupture"]
    e += [Paragraph("Les 15 provinces au taux prévu le plus élevé", S["h2"]),
          _tableau(lignes, [12, 28, 24, 22, 22, 28, 16, 18], couleurs)]

    r = n["resistantes"]
    e += [KeepTogether([Paragraph("Provinces qui résistent", S["h2"]),
                        Paragraph("Leur niveau habituel d'abandon est nettement plus bas que celui attendu d'après leurs caractéristiques "
                                  "(prédiction faite sans voir la province). Leurs pratiques méritent d'être étudiées.", S["corps"]),
                        _tableau([["Province", "Région", "Niveau observé", "Niveau attendu", "Écart"]]
                                 + [[x["province"], x["region"], _pct(x["observe"]), _pct(x["attendu"]), f"−{fr(abs(x['ecart']))} pt"] for x in r],
                                 [40, 35, 33, 33, 25])])]

    imp = D.explication("importance", population).head(6)
    e += [KeepTogether([Paragraph("Facteurs associés au risque", S["h2"])]
                       + [Paragraph(f"<b>{x['libelle']}</b> : {x['sens']} (contribution moyenne {fr(x['contribution_absolue_moyenne_points'], 2)} point)", S["puce"], bulletText="•")
                          for _, x in imp.iterrows()])]

    positives = [x["variable"] for _, x in imp.iterrows() if "élevé" in x["sens"].split(",")[-1]]
    e += [KeepTogether([Paragraph("Pistes d'action", S["h2"]),
                        Paragraph(f"<b>Priorité géographique</b> : les provinces à la fois en risque élevé et en alerte de rupture "
                                  f"({', '.join(p['province'] for p in provinces if p['serie'][k]['classe'] == 'élevé' and p['rupture'] == 'élevé')}).", S["puce"], bulletText="•")]
                       + [Paragraph(t, S["puce"], bulletText="•") for t in _pistes(positives, rupture=bool(ruptures))]
                       + [Paragraph(f"<b>Apprendre des provinces qui résistent</b> : {', '.join(x['province'] for x in r[:3])}.", S["puce"], bulletText="•")])]
    e += _sources(population)
    doc.build(e, onFirstPage=pied, onLaterPages=pied)
    return tampon.getvalue()


def rapport_province(pcode: str, population: str = "ensemble") -> bytes:
    from main import province, national
    p = province(pcode, population)
    n = national(population)
    r, ident = p["prevision"], p["identite"]
    doc, tampon, pied = _document(f"Rapport {ident['province']}")
    region = [x for x in n["provinces"] if x["region"] == ident["region"]]
    def pondere(liste):
        w = sum(x["poids"] or 1 for x in liste)
        return sum((x["serie"][1]["taux"] or 0) * (x["poids"] or 1) for x in liste) / w

    e = [Paragraph(f"{ident['province']}", S["titre"]),
         Paragraph(f"Région {ident['region']}{' · province créée en 2025 (ex-' + ident['ancienne_province'] + ')' if ident['scindee'] else ''}"
                   f" · prévision 2025-2026 · {POPULATIONS[population]}", S["sous"]),
         _chiffres([(_pct(r["taux_actuel"]), "observé 2024-2025", GRIS),
                    (_pct(r["taux"]), f"prévu 2025-2026 {_ic(r['borne_basse'], r['borne_haute'])}", COULEURS[r["classe"]]),
                    (f"{ident['rang']}{'er' if ident['rang'] == 1 else 'e'} / {ident['provinces']}", f"risque {r['classe']}", COULEURS[r["classe"]]),
                    (fr(p["rupture"]["score"], 2), f"score de rupture ({p['rupture']['classe']})", "#7c3aed")]),
         Paragraph("Synthèse", S["h2"]), Paragraph(p["synthese"], S["corps"]),
         Paragraph(f"Repères 2025-2026 : région {ident['region']} {_pct(pondere(region))}, pays {_pct(pondere(n['provinces']))} (moyennes pondérées par les effectifs).", S["corps"]),
         Paragraph("Évolution et prévisions", S["h2"]), _image(_historique(p), 165),
         Paragraph("Bandes violettes : années de rupture, écartées du calcul du niveau habituel.", S["petit"]),
         Paragraph("Ce qui place son niveau au-dessus ou au-dessous de la moyenne", S["h2"]), _image(_cascade(p), 165)]

    sexe = p["par_sexe"]
    if sexe:
        e += [Paragraph("Filles et garçons, 2025-2026", S["h2"]),
              _tableau([["", "Taux prévu", "Intervalle à 80 %", "Classe"]]
                       + [[("Filles" if s == "F" else "Garçons"), _pct(x["taux"]), _ic(x["borne_basse"], x["borne_haute"]), x["classe"]] for s, x in sexe.items()],
                       [30, 30, 40, 25], {(i + 1, 3): x["classe"] for i, x in enumerate(sexe.values())})]

    signaux = ", ".join(s["signal"] for s in p["rupture"]["signaux"][:3] if s["contribution"] > 0)
    e += [Paragraph("Risque de rupture de scolarisation", S["h2"]),
          Paragraph(f"Score {fr(p['rupture']['score'], 2)} sur 1 ({p['rupture']['classe']}). Signaux qui l'augmentent : {signaux or 'aucun'}.", S["corps"])]
    positives = [c["variable"] for c in p["cascade"]["contributions"] if c["contribution"] > 0]
    pistes = _pistes(positives, rupture=p["rupture"]["classe"] == "élevé")
    if pistes:
        e += [KeepTogether([Paragraph("Pistes d'action", S["h2"])] + [Paragraph(t, S["puce"], bulletText="•") for t in pistes])]
    e += _sources(population)
    doc.build(e, onFirstPage=pied, onLaterPages=pied)
    return tampon.getvalue()


def rapport_region(nom: str, population: str = "ensemble") -> bytes:
    from main import national
    n = national(population)
    provinces = sorted([x for x in n["provinces"] if x["region"] == nom], key=lambda x: -(x["serie"][1]["taux"] or 0))
    if not provinces:
        raise ValueError(f"Région inconnue : {nom}")
    doc, tampon, pied = _document(f"Rapport région {nom}")
    w = sum(x["poids"] or 1 for x in provinces)
    moyenne = sum((x["serie"][1]["taux"] or 0) * (x["poids"] or 1) for x in provinces) / w
    eleve = [x for x in provinces if x["serie"][1]["classe"] == "élevé"]
    ruptures = [x for x in provinces if x["rupture"] == "élevé"]
    e = [Paragraph(f"Région {nom}", S["titre"]),
         Paragraph(f"Rapport régional · {len(provinces)} provinces · prévision 2025-2026 · {POPULATIONS[population]}", S["sous"]),
         _chiffres([(_pct(moyenne), "taux régional prévu (pondéré)", VERT), (f"{len(eleve)} / {len(provinces)}", "provinces en risque élevé", COULEURS["élevé"]),
                    (str(len(ruptures)), "alertes de rupture", "#7c3aed"), (provinces[0]["province"], "province la plus exposée", COULEURS["élevé"])]),
         Paragraph("Carte", S["h2"]), _image(_carte(population, region=nom), 105)]
    lignes = [["Province", "Observé 2024-2025", "Prévu 2025-2026", "Intervalle à 80 %", "Classe", "Score de rupture"]]
    couleurs = {}
    for i, x in enumerate(provinces, start=1):
        s0, s1 = x["serie"][0], x["serie"][1]
        lignes.append([x["province"], _pct(s0["taux"]), _pct(s1["taux"]), _ic(s1["bas"], s1["haut"]), s1["classe"], fr(x["score_rupture"], 2)])
        couleurs[(i, 4)] = s1["classe"]
    e += [Paragraph("Provinces de la région", S["h2"]), _tableau(lignes, [36, 28, 28, 34, 22, 26], couleurs)]
    from main import _cascade
    priorites = []
    for x in provinces:
        if x["serie"][1]["classe"] == "élevé" or x["rupture"] == "élevé":
            c = _cascade(x["pcode"], population, n=3)
            facteurs = ", ".join(f["libelle"] for f in c["contributions"] if f["contribution"] > 0) or "pas de facteur au-dessus de la moyenne"
            priorites.append(Paragraph(f"<b>{x['province']}</b> : {_pct(x['serie'][1]['taux'])}"
                                       f"{', alerte de rupture' if x['rupture'] == 'élevé' else ''} ; facteurs : {facteurs}.", S["puce"], bulletText="•"))
    if priorites:
        e += [KeepTogether([Paragraph("Provinces à prioriser", S["h2"])] + priorites)]
    variables = []
    for x in provinces[:3]:
        variables += [f["variable"] for f in _cascade(x["pcode"], population, n=4)["contributions"] if f["contribution"] > 0]
    pistes = _pistes(variables, rupture=bool(ruptures))
    if pistes:
        e += [KeepTogether([Paragraph("Pistes d'action", S["h2"])] + [Paragraph(t, S["puce"], bulletText="•") for t in pistes])]
    e += _sources(population)
    doc.build(e, onFirstPage=pied, onLaterPages=pied)
    return tampon.getvalue()
