"""Notice d'usage de l'intelligence artificielle, au format PDF (règle d'or du document du challenge, section 7).

Lancement, depuis ``docs/notice_ia`` : ``python notice_ia.py`` ; sortie : ``notice_usage_ia.pdf``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parents[1] / "application" / "api"))
import rapport as R  # noqa: E402  (polices et styles communs aux documents de la solution)

S = R.S
SORTIE = ICI / "notice_usage_ia.pdf"

TABLEAU = [
    ["Outil", "Ce que nous lui avons demandé", "Ce que nous en avons retenu"],
    ["Assistant de programmation (Claude, Anthropic)",
     "Écrire et corriger du code Python et du site web, proposer une organisation des modules, mettre en forme la "
     "documentation LaTeX, préparer le déploiement.",
     "Le code relu, testé (17 tests automatiques) et exécuté ; les propositions inexactes ont été corrigées ou "
     "écartées."],
    ["Gemini (Google), dans l'application",
     "Répondre en français aux questions d'un décideur, à partir des fonctions de notre API.",
     "Il ne reçoit que des indicateurs agrégés par province ; ses chiffres viennent de nos fonctions ; un mode hors "
     "ligne sans IA donne les mêmes réponses."],
]


def construire() -> Path:
    e = [Paragraph("Notice d'usage de l'intelligence artificielle", S["titre"]),
         Paragraph("Sentinelle Scolaire · Défi 1 · cartographie et anticipation du risque de décrochage scolaire", S["sous"])]

    e += [Paragraph("1. Les données utilisées ne sont pas sensibles", S["h2"]),
          Paragraph("Toutes les données de la solution sont des <b>statistiques publiques agrégées</b> par commune, "
                    "province, région ou pays : base principale de la DGESS remise par les organisateurs, annuaires et "
                    "tableaux de bord de la DGESS, recensement et projections de l'INSD, contours administratifs et "
                    "données humanitaires publiques (OCHA, ST-ESU, SP/CONASUR). Elles ne contiennent <b>aucune donnée "
                    "individuelle ni nominative</b> : aucun élève, enseignant ou ménage n'y est identifiable. Elles ont "
                    "été utilisées uniquement pour le concours.", S["corps"])]

    e += [Paragraph("2. Ce que nous avons fait nous-mêmes", S["h2"])]
    e += [Paragraph(t, S["puce"], bulletText="•") for t in [
        "La question posée, le choix des sources et la lecture critique de chacune (registre et bilan des sources).",
        "Les règles de nettoyage et de passage au découpage de 2025, et leur contrôle : totaux comparés aux "
        "publications d'origine, cohérence filles-garçons, contrôle de chaque jointure.",
        "La règle de choix du modèle, écrite avant de voir l'année de test, et le refus d'un modèle plus complexe "
        "(LightGBM) qui ne gagnait que par chance sur les années de sélection.",
        "La décision de ne pas prévoir le post-primaire et le secondaire (quatre années publiées seulement) et le "
        "traitement des taux de 0 non renseignés dans les annuaires.",
        "La relecture de chaque résultat, de chaque chiffre du rapport et de chaque écran du tableau de bord.",
    ]]

    e += [Paragraph("3. Ce que nous avons demandé à l'IA et ce que nous en avons retenu", S["h2"])]
    donnees = [[Paragraph(c, S["cellule"]) for c in ligne] for ligne in TABLEAU]
    t = Table(donnees, colWidths=[40 * mm, 66 * mm, 66 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f3ec")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d3df")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    e += [t, Spacer(1, 4)]
    e += [Paragraph("L'assistant de programmation travaillait dans notre environnement de travail, sur ces données "
                    "publiques agrégées, pour exécuter et vérifier le code : ce sont les seules données qu'il a "
                    "traitées, et aucune donnée individuelle n'existe dans nos sources.", S["corps"])]

    e += [Paragraph("4. Comment nous avons gardé l'esprit critique", S["h2"])]
    e += [Paragraph(t, S["puce"], bulletText="•") for t in [
        "Chaque chiffre affiché vient du code de la solution, jamais d'un texte rédigé par une IA.",
        "Les prévisions sont évaluées sur une année jamais vue par les modèles (2024-2025), avec des intervalles dont "
        "la couverture est vérifiée.",
        "17 tests automatiques contrôlent les calculs clés et la cohérence entre l'analyse et l'application.",
        "Toutes les sources sont citées : producteur, publication, année, dans le rapport et les LISEZ-MOI.",
    ]]
    doc = SimpleDocTemplate(str(SORTIE), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title="Notice d'usage de l'IA",
                            author="Sentinelle Scolaire")
    doc.build(e)
    return SORTIE


if __name__ == "__main__":
    print(construire())
