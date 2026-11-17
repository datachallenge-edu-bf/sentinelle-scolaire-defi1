"use client";

import { useEffect, useState } from "react";
import { IconeLecture, IconePause } from "./Icones";

/** Choix de l'année affichée : observé 2024-2025 puis prévisions ; le bouton lecture fait défiler les années. */
export default function CurseurAnnees({
  annees,
  valeur,
  changer,
}: {
  annees: string[];
  valeur: number;
  changer: (k: number) => void;
}) {
  const [lecture, setLecture] = useState(false);
  useEffect(() => {
    if (!lecture) return;
    const minuterie = setInterval(() => changer((valeur + 1) % annees.length), 1400);
    return () => clearInterval(minuterie);
  }, [lecture, valeur, annees.length, changer]);

  return (
    <div className="curseur-annees" role="radiogroup" aria-label="Année affichée">
      <button
        className="bouton-lecture"
        onClick={() => setLecture(!lecture)}
        aria-label={lecture ? "Arrêter le défilement" : "Faire défiler les années"}
      >
        {lecture ? <IconePause /> : <IconeLecture />}
      </button>
      {annees.map((a, k) => (
        <button
          key={a}
          role="radio"
          aria-checked={k === valeur}
          className={k === valeur ? "actif" : ""}
          onClick={() => {
            setLecture(false);
            changer(k);
          }}
        >
          <b>{a}</b>
          <span>{k === 0 ? "observé" : `prévision ${k} an${k > 1 ? "s" : ""}`}</span>
        </button>
      ))}
    </div>
  );
}
