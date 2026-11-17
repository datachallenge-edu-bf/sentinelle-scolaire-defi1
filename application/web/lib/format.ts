import type { Classe, Population } from "./api";

/** Couleurs des classes de risque (validées contre le daltonisme sur la surface sombre). */
export const COULEURS_CLASSES: Record<Classe, string> = {
  faible: "#2a9d74",
  moyen: "#cf8a1a",
  élevé: "#d93a63",
};

/** Filles et garçons : deux teintes séparables par tous les lecteurs, distinctes des classes de risque. */
export const COULEURS_SEXE = { F: "#d0702f", G: "#3b82f6" } as const;

export const LIBELLES_CLASSES: Record<Classe, string> = { faible: "Faible", moyen: "Moyen", élevé: "Élevé" };

export const LIBELLES_POPULATIONS: Record<Population, string> = {
  ensemble: "Ensemble",
  F: "Filles",
  G: "Garçons",
};

export function nombre(x: number | null | undefined, decimales = 1): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "n.d.";
  return x.toLocaleString("fr-FR", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
}

export function pourcent(x: number | null | undefined, decimales = 1): string {
  return `${nombre(x, decimales)} %`;
}

export function intervalle(bas: number, haut: number, decimales = 1): string {
  return `[${nombre(bas, decimales)} ; ${nombre(haut, decimales)}]`;
}

export function classeDe(taux: number, seuils: { moyen: number; eleve: number }): Classe {
  return taux >= seuils.eleve ? "élevé" : taux >= seuils.moyen ? "moyen" : "faible";
}

export function avecPopulation(chemin: string, population: Population): string {
  return population === "ensemble" ? chemin : `${chemin}?population=${population}`;
}
