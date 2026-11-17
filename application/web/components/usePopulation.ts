"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import type { Population } from "@/lib/api";

/** Population affichée (ensemble, filles, garçons), gardée dans l'adresse pour pouvoir partager une vue. */
export function usePopulation(): [Population, (p: Population) => void] {
  const parametres = useSearchParams();
  const routeur = useRouter();
  const chemin = usePathname();
  const brute = parametres.get("population");
  const population: Population = brute === "F" || brute === "G" ? brute : "ensemble";
  const changer = useCallback(
    (p: Population) => {
      const suite = new URLSearchParams(parametres.toString());
      if (p === "ensemble") suite.delete("population");
      else suite.set("population", p);
      const requete = suite.toString();
      routeur.replace(requete ? `${chemin}?${requete}` : chemin, { scroll: false });
    },
    [parametres, routeur, chemin],
  );
  return [population, changer];
}
