"use client";

import type { Population } from "@/lib/api";
import { LIBELLES_POPULATIONS } from "@/lib/format";

export default function BasculePopulation({
  valeur,
  changer,
}: {
  valeur: Population;
  changer: (p: Population) => void;
}) {
  return (
    <div className="bascule" role="radiogroup" aria-label="Population affichée">
      {(["ensemble", "F", "G"] as Population[]).map((p) => (
        <button
          key={p}
          role="radio"
          aria-checked={valeur === p}
          className={valeur === p ? "actif" : ""}
          onClick={() => changer(p)}
        >
          {LIBELLES_POPULATIONS[p]}
        </button>
      ))}
    </div>
  );
}
