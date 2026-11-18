"""Tests de Sentinelle Scolaire : calculs clés, cohérence entre l'analyse et l'application, livrables.

Lancement, depuis ``defi1_sentinelle`` : ``python -m pytest`` (chemins déclarés dans ``pyproject.toml``).
Les tests lisent les sorties de l'étape 04 (``data/04_analyse``) : ils ne demandent pas les données des
organisateurs.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest

from sentinelle import config, depots
from sentinelle.analyse import preparation as P


# Normalisation de la cible ------------------------------------------------------------------------

def test_normalisation_aller_retour():
    taux = np.array([0.5, 1.0, 8.4, 25.4, 60.0, 99.5])
    assert np.allclose(P.denormaliser(P.normaliser(taux)), taux, atol=1e-9)


def test_denormalisation_toujours_entre_0_et_100():
    z = np.linspace(-20, 20, 101)
    t = P.denormaliser(z)
    assert t.min() >= 0 and t.max() <= 100


# Nommage des dépôts ----------------------------------------------------------------------------------

MODELE = re.compile(r"^SENTINELLE_0[1-5]-[a-z]+_D1_(engineer|architect|analyst|scientist)_[a-z0-9]+(-[a-z0-9]+)*_v[0-9]+\.[a-z0-9]+$")


def test_nom_depot_suit_la_convention():
    nom = depots.nom_depot(2, "engineer", "Effectifs primaire propres (édition 2025)", 1, "csv")
    assert nom == "SENTINELLE_02-nettoyage_D1_engineer_effectifs-primaire-propres-edition-2025_v1.csv"
    assert MODELE.match(nom)


def test_nom_depot_refuse_un_role_inconnu():
    with pytest.raises(ValueError):
        depots.nom_depot(1, "stagiaire", "x")


def test_tous_les_depots_sont_conformes():
    # Fichiers des dossiers de dépôt (le LISEZ-MOI général, à la racine de depots/, n'est pas un dépôt).
    fichiers = [f.name for d in config.DEPOTS.iterdir() if d.is_dir() for f in d.iterdir() if f.is_file()]
    if not fichiers:
        pytest.skip("dépôts non générés")
    assert [f for f in fichiers if not MODELE.match(f)] == []


# Application : données servies et cohérence avec l'analyse -------------------------------------------

@pytest.fixture(scope="module")
def api():
    import main
    return main


def test_vue_nationale_quatre_annees_47_provinces(api):
    n = api.national("ensemble")
    assert n["annees"] == ["2024-2025", "2025-2026", "2026-2027", "2027-2028"]
    assert len(n["provinces"]) == 47
    for p in n["provinces"]:
        for s in p["serie"][1:]:
            assert s["bas"] <= s["taux"] <= s["haut"]


def test_intervalle_ne_retrecit_pas_avec_l_horizon(api):
    import json
    fiche = json.loads((config.DONNEES / "04_analyse" / "modeles" / "ensemble" / "fiche_modele.json").read_text(encoding="utf-8"))
    marges = fiche["prevision"]["marge_conforme_logit_par_horizon"]
    assert marges["1"] <= marges["2"] <= marges["3"]


def test_fiche_province(api):
    p = api.province("BF5401", "ensemble")
    assert p["identite"]["province"] == "Loroum"
    assert len(p["projections"]) == 3
    cascade = p["cascade"]
    total = cascade["base"] + sum(c["contribution"] for c in cascade["contributions"]) + cascade["autres"]
    assert total == pytest.approx(cascade["niveau_explique"], abs=0.05)


def test_simulateur_reagit_aux_leviers(api):
    leviers = api.leviers("BF5401")
    valeurs = {v["variable"]: v["mediane_provinces"] for v in leviers["leviers"]}
    r = api.simuler(api.Scenario(pcode="BF5401", valeurs=valeurs))
    assert r["taux_simule"] < r["taux_prevu"]


def test_mise_a_jour_reproduit_exactement_l_analyse():
    """Sans nouvelle donnée, la mise à jour annuelle doit redonner les prévisions de l'analyse."""
    import mise_a_jour as M
    from donnees import DONNEES_APPLI as D
    a = M.calculer([])
    t = D.tableau_ensemble.set_index("province_pcode")
    r = pd.DataFrame(a["resultats"]).set_index("pcode")
    assert (r["avant"] - t["taux_abandon_prevu"]).abs().max() < 0.01
    for h, colonne in [(1, "taux_abandon_prevu_2026-2027"), (2, "taux_abandon_prevu_2027-2028")]:
        assert (r["previsions"].map(lambda x: x[h]["taux"]) - t[colonne]).abs().max() < 0.01
    assert (r["score_avant"] - t["score_rupture"]).abs().max() < 0.001


def test_mise_a_jour_detecte_les_erreurs():
    import mise_a_jour as M
    a = M.calculer([{"province_pcode": "XX", "taux_abandon_primaire": 5, "eleves_primaire": 10},
                    {"province_pcode": "BF5401", "taux_abandon_primaire": 150, "eleves_primaire": 20000}])
    erreurs = " ".join(m["texte"] for m in a["messages"] if m["niveau"] == "erreur")
    assert "XX" in erreurs and "BF5401" in erreurs


# Assistant -------------------------------------------------------------------------------------------

@pytest.fixture()
def hors_ligne(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_assistant_compare_deux_provinces(api, hors_ligne):
    from assistant import repondre
    r = repondre("Compare Loroum et Yagha")
    assert r["mode"] == "hors ligne"
    assert "Loroum" in r["reponse"] and "Yagha" in r["reponse"]
    assert {l["pcode"] for l in r["liens"]} == {"BF5401", "BF6403"}


def test_assistant_reprend_la_zone_de_l_echange_precedent(api, hors_ligne):
    from assistant import repondre
    historique = [{"auteur": "moi", "texte": "Que se passe-t-il dans la région Liptako ?"}]
    r = repondre("Quel est le niveau de pauvreté dans la zone ?", "ensemble", historique)
    assert "Liptako" in r["reponse"] and "pauvreté" in r["reponse"]


def test_mots_cles_ne_se_confondent_pas():
    import indicateurs as I
    assert "part_ecoles_primaires_eau_potable" not in I.variables_de_la_question("niveau de pauvreté")
    assert I.variables_de_la_question("mariage précoce")[:1] == ["filles_17_ans_mariees_province"]


# Livrables -------------------------------------------------------------------------------------------

def test_rapport_province_est_un_pdf(api):
    import rapport
    contenu = rapport.rapport_province("BF5401", "ensemble")
    assert contenu[:4] == b"%PDF" and len(contenu) > 50_000
