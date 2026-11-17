"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { Alerte, Population } from "@/lib/api";
import { avecPopulation, nombre, pourcent } from "@/lib/format";
import { IconeAlerte, IconeFermer } from "./Icones";

/** Bouton à compteur dans l'en-tête ; un clic ouvre le panneau latéral des alertes. */
export default function TiroirAlertes({ alertes, population }: { alertes: Alerte[]; population: Population }) {
  const [ouvert, setOuvert] = useState(false);
  const routeur = useRouter();
  useEffect(() => {
    const echap = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOuvert(false);
    };
    window.addEventListener("keydown", echap);
    return () => window.removeEventListener("keydown", echap);
  }, []);
  const ruptures = alertes.filter((a) => a.type === "rupture");
  const hausses = alertes.filter((a) => a.type === "hausse");
  const ouvrir = (pcode: string) => {
    setOuvert(false);
    routeur.push(avecPopulation(`/province/${pcode}`, population));
  };

  return (
    <>
      <button className="cloche" onClick={() => setOuvert(true)} aria-label={`${alertes.length} alertes`}>
        <IconeAlerte taille={18} />
        Alertes
        <span className="compteur">{alertes.length}</span>
      </button>
      {ouvert ? <div className="voile" onClick={() => setOuvert(false)} /> : null}
      <aside className={`tiroir${ouvert ? " ouvert" : ""}`} aria-hidden={!ouvert} aria-label="Alertes à suivre">
        <div className="tiroir-entete">
          <h2>Alertes à suivre</h2>
          <button className="bouton-icone" onClick={() => setOuvert(false)} aria-label="Fermer">
            <IconeFermer />
          </button>
        </div>
        <h3>
          <span className="point" style={{ background: "#8b5cf6" }} /> Rupture de scolarisation probable ({ruptures.length})
        </h3>
        <ul className="liste-tiroir">
          {ruptures.map((a) => (
            <li key={`r-${a.pcode}`}>
              <button onClick={() => ouvrir(a.pcode)}>
                <span>
                  <b>{a.province}</b>
                  <small>{a.region}</small>
                </span>
                <span className="valeur-alerte">score {nombre(a.valeur, 2)}</span>
              </button>
            </li>
          ))}
        </ul>
        <h3>
          <span className="point" style={{ background: "#d93a63" }} /> Risque élevé en hausse ({hausses.length})
        </h3>
        <ul className="liste-tiroir">
          {hausses.map((a) => (
            <li key={`h-${a.pcode}`}>
              <button onClick={() => ouvrir(a.pcode)}>
                <span>
                  <b>{a.province}</b>
                  <small>{a.region}</small>
                </span>
                <span className="valeur-alerte">
                  {pourcent(a.avant ?? null)} → {pourcent(a.valeur)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </>
  );
}
