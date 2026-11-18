"""Guide d'utilisation de Sentinelle Scolaire, au format PDF.

Produit ``application/web/public/guide_sentinelle.pdf`` (téléchargeable depuis la barre latérale) à partir des
captures d'écran de ``application/guide/images/``. Lancement, depuis ``application/guide`` :
``python guide.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, Spacer

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "api"))
import rapport as R  # noqa: E402  (mise en forme commune : polices, styles, pied de page)

S = R.S
IMAGES = ICI / "images"
SORTIE = ICI.parent / "web" / "public" / "guide_sentinelle.pdf"


def capture(nom: str, largeur_mm: float = 178) -> Image:
    from PIL import Image as PILImage
    chemin = IMAGES / f"{nom}.jpg"
    l, h = PILImage.open(chemin).size
    return Image(str(chemin), width=largeur_mm * R.mm, height=largeur_mm * R.mm * h / l)


def puces(textes: list[str]) -> list:
    return [Paragraph(t, S["puce"], bulletText="•") for t in textes]


def ecran(titre: str, image: str, texte: str, gestes: list[str]) -> list:
    return [KeepTogether([Paragraph(titre, S["h2"]), Paragraph(texte, S["corps"]), capture(image), Spacer(1, 4)]
                         + puces(gestes))]


def construire() -> Path:
    doc, tampon, pied = R._document("Guide d'utilisation")
    e = [Paragraph("Sentinelle Scolaire", S["titre"]),
         Paragraph("Guide d'utilisation du tableau de bord du risque de décrochage scolaire au primaire", S["sous"]),
         Paragraph("À quoi sert le dispositif", S["h2"]),
         Paragraph("Sentinelle Scolaire repère les provinces où le décrochage au primaire risque d'être le plus élevé, explique "
                   "ce qui les distingue et signale celles qui risquent une rupture de scolarisation (fermetures d'écoles, "
                   "déplacements). Il sert à choisir où agir en premier, avec quels leviers, et à préparer des rapports pour la "
                   "décision. Il couvre les 47 provinces et les 17 régions du découpage de 2025.", S["corps"]),
         Paragraph("Lire les chiffres", S["h2"])]
    e += puces([
        "<b>Taux d'abandon</b> : part des élèves du primaire qui quittent l'école au cours d'une année. L'année 2024-2025 est "
        "observée (dernier annuaire) ; 2025-2026, 2026-2027 et 2027-2028 sont des prévisions.",
        "<b>Prévision</b> : une province au-dessus (ou au-dessous) de son niveau habituel en 2024-2025 y revient "
        "progressivement ; c'est pourquoi les taux évoluent d'une année à l'autre puis se stabilisent.",
        "<b>Intervalle à 80 %</b> : fourchette dans laquelle le taux réel tombe 8 fois sur 10. Il ne rétrécit pas avec l'horizon. "
        "La classe de risque est plus fiable que le chiffre exact.",
        "<b>Classes de risque</b> : faible sous 8,4 %, moyen de 8,4 à 14,2 %, élevé au-delà (médiane et 80e centile des taux prévus).",
        "<b>Alerte de rupture</b> : probabilité d'une variation des effectifs de plus de 30 % l'an prochain ; élevée au-dessus de 0,6.",
        "<b>Facteurs (SHAP)</b> : ce qui place le niveau habituel d'une province au-dessus (rouge) ou au-dessous (vert) de la "
        "moyenne, en points de taux. Ce sont des associations, pas des causes.",
        "<b>Provinces qui résistent</b> : provinces dont le niveau réel est nettement sous celui attendu d'après leurs "
        "caractéristiques. Leurs pratiques sont à étudier.",
        "<b>Ensemble, filles, garçons</b> : chaque écran propose les trois vues (bascule en haut à droite).",
    ])
    e += [PageBreak()]
    e += ecran("1. Vue nationale", "1_nationale",
               "L'écran d'accueil : chiffres clés, carte des classes de risque, facteurs, classement des 47 provinces, filles et "
               "garçons, provinces qui résistent, évolution des classes d'une année à l'autre.",
               ["Choisissez l'année avec le curseur (2024-2025 observé, puis prévisions) ; le bouton lecture fait défiler les années.",
                "Survolez une province pour voir son taux et son intervalle ; zoomez pour lire les noms ; cliquez pour ouvrir sa fiche.",
                "Le bouton « Rapport » télécharge le rapport national en PDF ; le bouton « Données » télécharge la base des "
                "prévisions 2025-2028 (CSV qui s'ouvre dans Excel) : taux, intervalle, classe, abandons estimés et risque de "
                "rupture de chaque province, pour la population choisie."])
    e += ecran("2. Alertes", "6_alertes",
               "Le bouton « Alertes » ouvre la liste des provinces en alerte de rupture et de celles dont le risque élevé augmente.",
               ["Cliquez une province pour ouvrir sa fiche ; Échap ferme le panneau."])
    e += ecran("3. Fiche province", "2_province",
               "Tout ce qu'il faut savoir sur une province, sur un seul écran : taux observé et prévu, classe et rang, score de "
               "rupture, historique depuis 2016-2017 avec les prévisions, facteurs SHAP, filles et garçons.",
               ["Accès : clic sur la carte, sur un classement, ou liste « Aller à une province » dans la barre latérale.",
                "« Rapport PDF » produit la fiche de décision de la province, avec ses pistes d'action."])
    e += ecran("4. Vue régions", "3_regions",
               "Taux de chaque région (moyenne de ses provinces pondérée par les effectifs), classement, provinces de la région choisie.",
               ["Cliquez une région sur la carte ou dans le classement ; « Rapport » télécharge le rapport régional, "
                "« Données » les prévisions de ses provinces en CSV."])
    e += ecran("5. Simulateur de leviers", "8_simulateur_scenario",
               "Que deviendrait le taux attendu d'une province si ses caractéristiques changeaient ? Les effets viennent du modèle "
               "linéaire validé sur des provinces non vues (il explique 64 % des écarts entre provinces).",
               ["Déplacez les curseurs, ou « Aligner sur la médiane » pour comparer à la province médiane du pays.",
                "Résultat à lire comme un ordre de grandeur pour fixer des priorités, pas comme un effet garanti."])
    e += ecran("6. Mise à jour des données", "9_mise_a_jour_apercu",
               "Chaque année, à la sortie de l'annuaire, les prévisions des trois années suivantes se recalculent sans réentraîner les "
               "modèles. Les données saisies sont rangées à part (data/05_mises_a_jour) et ne modifient jamais les données officielles.",
               ["Téléchargez le « Modèle CSV à remplir » (47 provinces, valeurs de l'année précédente pour repère), ou saisissez à l'écran.",
                "Renseignez le taux d'abandon et l'effectif du primaire (filles et garçons facultatifs), puis « Calculer les prévisions ».",
                "Vérifiez les contrôles (provinces manquantes, valeurs hors limites, ruptures détectées) et les changements de classe.",
                "« Enregistrer » range les données et télécharge les nouvelles prévisions ; « retirer » annule la dernière année saisie."])
    e += ecran("7. Assistant Sentinelle", "7_assistant",
               "Le bouton « Demander à Sentinelle », en bas à droite, répond aux questions de décision à partir des données : "
               "priorités, comparaison de provinces, situation d'une région, ruptures, provinces qui résistent, filles et garçons.",
               ["Chaque réponse donne ses sources et des liens vers les fiches des provinces citées.",
                "Sans connexion, l'assistant répond en mode hors ligne. Avec une clé Gemini (variable GEMINI_API_KEY), les réponses "
                "sont rédigées par le modèle à partir des mêmes outils, sans autre source de chiffres."])
    e += [Paragraph("Installer et lancer", S["h2"])]
    e += puces(["API (port 8000), depuis application/api : <font face='Courier'>python -m uvicorn main:app --port 8000</font>.",
                "Site (port 3000), depuis application/web : <font face='Courier'>npm install</font>, "
                "<font face='Courier'>npm run build</font>, puis <font face='Courier'>npm start</font> ; ouvrir http://localhost:3000.",
                "Réentraîner les modèles avec les nouvelles années (conseillé tous les deux ou trois ans) : relancer "
                "<font face='Courier'>sentinelle.analyse.executer_modelisation()</font> après l'apurement."])
    e += [Paragraph("Limites", S["h2"])]
    e += puces(["Huit à neuf années par province : la prévision retenue part du niveau habituel de la province, vers lequel "
                "l'écart de la dernière année revient progressivement ; les modèles plus complexes ne font pas mieux.",
                "Les provinces créées en 2025 héritent de l'historique de leur ancienne province.",
                "Les effectifs par sexe de 2024-2025 sont incohérents dans les sources et ne sont pas utilisés.",
                "Les facteurs et le simulateur décrivent des associations entre provinces, pas des effets causaux."])
    e += R._sources()
    doc.build(e, onFirstPage=pied, onLaterPages=pied)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_bytes(tampon.getvalue())
    return SORTIE


if __name__ == "__main__":
    print(construire())
