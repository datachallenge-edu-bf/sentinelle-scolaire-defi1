"use client";

import { nombre } from "@/lib/format";

/** Une case par province : les cases de la classe sont pleines, les autres en creux. */
export function Bande47({ total, compte, couleur }: { total: number; compte: number; couleur: string }) {
  return (
    <div className="bande" role="img" aria-label={`${compte} provinces sur ${total}`}>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} style={i < compte ? { background: couleur, borderColor: couleur } : undefined} />
      ))}
    </div>
  );
}

/** Courbe miniature : historique (trait plein) puis prévision (pointillé), dernier point marqué. */
export function Courbe({
  historique,
  prevision,
  couleur = "#2fbf7f",
  largeur = 150,
  hauteur = 34,
}: {
  historique: (number | null)[];
  prevision: number[];
  couleur?: string;
  largeur?: number;
  hauteur?: number;
}) {
  const tout = [...historique, ...prevision];
  const valeurs = tout.filter((v): v is number => v !== null);
  const min = Math.min(...valeurs, 0);
  const max = Math.max(...valeurs, 1);
  const x = (i: number) => 3 + (i * (largeur - 6)) / Math.max(1, tout.length - 1);
  const y = (v: number) => hauteur - 4 - ((v - min) * (hauteur - 8)) / (max - min || 1);
  const n = historique.length;
  let plein = "";
  let leve = true;
  historique.forEach((v, i) => {
    if (v === null) {
      leve = true;
      return;
    }
    plein += `${leve ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    leve = false;
  });
  let dernier = n - 1;
  while (dernier > 0 && historique[dernier] === null) dernier--;
  const depart = historique[dernier] ?? prevision[0];
  const pointille =
    `M${x(dernier).toFixed(1)},${y(depart).toFixed(1)}` + prevision.map((v, j) => `L${x(n + j).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const fin = tout.length - 1;
  return (
    <svg width={largeur} height={hauteur} viewBox={`0 0 ${largeur} ${hauteur}`} aria-hidden="true">
      <path d={plein} fill="none" stroke={couleur} strokeWidth={1.8} />
      <path d={pointille} fill="none" stroke={couleur} strokeWidth={1.8} strokeDasharray="3 3" />
      <circle cx={x(fin)} cy={y(prevision[prevision.length - 1] ?? depart)} r={3} fill={couleur} />
    </svg>
  );
}

/** Deux barres : l'erreur de Sentinelle et celle de la méthode naïve (taux de l'année précédente). */
export function Comparaison({ nous, naif }: { nous: number; naif: number }) {
  const max = Math.max(nous, naif);
  return (
    <div className="comparaison">
      <div>
        <span>Sentinelle</span>
        <div className="piste-fine">
          <div style={{ width: `${(100 * nous) / max}%`, background: "#2fbf7f" }} />
        </div>
        <b>{nombre(nous)}</b>
      </div>
      <div>
        <span>Année précédente</span>
        <div className="piste-fine">
          <div style={{ width: `${(100 * naif) / max}%`, background: "#64748b" }} />
        </div>
        <b>{nombre(naif)}</b>
      </div>
    </div>
  );
}
