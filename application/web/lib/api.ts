"use client";

import { useEffect, useState } from "react";

export type Population = "ensemble" | "F" | "G";
export type Classe = "faible" | "moyen" | "élevé";

export interface Resume {
  pcode: string;
  province: string;
  region: string;
  taux: number;
  borne_basse: number;
  borne_haute: number;
  classe: Classe;
  taux_actuel: number | null;
  hausse: boolean;
  score_rupture: number;
  rupture: Classe;
  scindee: boolean;
  ancienne_province: string;
}

export interface Seuils {
  moyen: number;
  eleve: number;
}

export interface Meta {
  annee_prevue: string;
  annees_projetees: string[];
  annee_des_variables: string;
  populations: Record<Population, string>;
  date_modele: string;
  sources: string[];
  provinces: { pcode: string; province: string; region: string }[];
  regions: string[];
}

export interface Carte {
  provinces: GeoJSON.FeatureCollection;
  regions: GeoJSON.FeatureCollection;
  etiquettes_regions: Record<string, [number, number]>;
  etiquettes_provinces: Record<string, [number, number]>;
  seuils: Seuils;
}

export interface PointSerie {
  annee: string;
  nature: "observé" | "prévision";
  taux: number | null;
  bas: number | null;
  haut: number | null;
  classe: Classe | null;
}

export interface ProvinceNationale {
  pcode: string;
  province: string;
  region: string;
  scindee: boolean;
  ancienne_province: string;
  score_rupture: number;
  rupture: Classe;
  poids: number;
  serie: PointSerie[];
  historique: (number | null)[];
}

export interface Alerte {
  pcode: string;
  province: string;
  region: string;
  type: "rupture" | "hausse";
  valeur: number;
  avant?: number;
}

export interface National {
  population: Population;
  annees: string[];
  annees_historique: string[];
  seuils: Seuils;
  provinces: ProvinceNationale[];
  alertes: Alerte[];
  sexe_par_region: { region: string; filles: number | null; garcons: number | null }[][];
  nuage_shap: {
    variables: { variable: string; libelle: string }[];
    points: { v: number; pcode: string; province: string; shap: number; valeur: number | null; rang: number | null }[];
  };
  resistantes: { pcode: string; province: string; region: string; observe: number; attendu: number; ecart: number }[];
  erreurs: { sentinelle: number; annee_precedente: number };
}

export interface PointHistorique {
  annee: string;
  taux: number;
  observe: boolean;
  rupture: boolean;
}

export interface Projection {
  annee: string;
  horizon: number;
  taux: number;
  borne_basse: number;
  borne_haute: number;
}

export interface Province {
  population: Population;
  identite: {
    pcode: string;
    province: string;
    region: string;
    ancienne_province: string;
    scindee: boolean;
    rang: number;
    provinces: number;
  };
  prevision: Resume;
  projections: Projection[];
  historique: Record<Population, PointHistorique[]>;
  cascade: {
    base: number;
    contributions: { variable: string; libelle: string; contribution: number; valeur: number | null }[];
    autres: number;
    niveau_explique: number;
    niveau_habituel_observe: number | null;
  };
  par_sexe: Partial<Record<"F" | "G", Resume>>;
  rupture: { score: number; classe: Classe; seuils: number[]; signaux: { signal: string; contribution: number }[] };
  synthese: string;
  seuils: Seuils;
  annee_des_variables: string;
}

export interface Region {
  region: string;
  provinces: number;
  taux_pondere: number;
  taux_max: number;
  province_max: string;
  eleve: number;
  moyen: number;
  faible: number;
  alertes_rupture: number;
  eleves_primaire: number;
}

export interface Leviers {
  pcode: string;
  province: string;
  region: string;
  taux: number;
  classe: Classe;
  r2: number;
  seuils: Seuils;
  leviers: {
    variable: string;
    libelle: string;
    unite: string;
    valeur: number;
    minimum: number;
    maximum: number;
    mediane_provinces: number;
    effet_par_unite: number;
  }[];
}

export interface Simulation {
  taux_prevu: number;
  taux_simule: number;
  ecart: number;
  classe_prevue: Classe;
  classe_simulee: Classe;
}

/** Requête GET sur l'API, relancée quand l'adresse change. */
export function useApi<T>(adresse: string | null) {
  const [donnees, setDonnees] = useState<T | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  useEffect(() => {
    if (!adresse) return;
    let actif = true;
    setErreur(null);
    fetch(adresse)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status} ${r.statusText}`))))
      .then((d) => actif && setDonnees(d))
      .catch((e) => actif && setErreur(String(e.message ?? e)));
    return () => {
      actif = false;
    };
  }, [adresse]);
  return { donnees, erreur };
}

export async function envoyer<T>(adresse: string, corps: unknown): Promise<T> {
  const r = await fetch(adresse, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
