"use client";

import { useApi, type ComparaisonOrdres as Donnees, type Population } from "@/lib/api";
import { pourcent } from "@/lib/format";

const ORDRES = [
  { cle: "primaire", libelle: "Primaire", couleur: "#3b82f6" },
  { cle: "post_primaire", libelle: "Post-primaire", couleur: "#e0a21b" },
  { cle: "secondaire", libelle: "Secondaire", couleur: "#a78bfa" },
] as const;

/** Abandon de la province médiane dans les trois ordres d'enseignement, années observées communes. */
export default function ComparaisonOrdres({ population }: { population: Population }) {
  const { donnees: d } = useApi<Donnees>(`/api/comparaison_ordres?population=${population}`);
  if (!d) return null;
  const dernier = d.annees.length - 1;
  const max = Math.max(...ORDRES.flatMap((o) => d.series[o.cle].map((v) => v ?? 0)), 1);
  return (
    <section className="panneau comparaison-ordres" aria-label="Comparaison des trois ordres d'enseignement">
      <div className="comparaison-chiffres">
        <div className="comparaison-titre">
          <b>Abandon · 3 ordres</b>
          <span className="note">province médiane, {d.annees[dernier]}</span>
        </div>
        {ORDRES.map((o) => {
          const v = d.series[o.cle][dernier];
          const avant = d.series[o.cle][0];
          return (
            <div key={o.cle} className="comparaison-ordre" style={{ "--teinte": o.couleur } as React.CSSProperties}>
              <span className="comparaison-libelle">{o.libelle}</span>
              <b>{pourcent(v)}</b>
              {avant != null && v != null ? (
                <span className="note">
                  {v >= avant ? "▲" : "▼"} {pourcent(avant)} en {d.annees[0]}
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
      <div className="comparaison-barres" role="img" aria-label="Évolution de l'abandon par ordre d'enseignement">
        {d.annees.map((a, k) => (
          <div key={a} className="comparaison-annee">
            <div className="comparaison-groupe">
              {ORDRES.map((o) => {
                const v = d.series[o.cle][k];
                return (
                  <span
                    key={o.cle}
                    title={`${o.libelle} ${a} : ${pourcent(v)}`}
                    style={{ height: `${(100 * (v ?? 0)) / max}%`, background: o.couleur }}
                  />
                );
              })}
            </div>
            <span className="note">{a}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
