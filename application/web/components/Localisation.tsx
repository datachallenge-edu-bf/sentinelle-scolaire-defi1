"use client";

import { useMemo } from "react";

type Anneau = number[][];

function anneaux(g: GeoJSON.Geometry): Anneau[] {
  if (g.type === "Polygon") return g.coordinates as Anneau[];
  if (g.type === "MultiPolygon") return (g.coordinates as Anneau[][]).flat();
  return [];
}

/** Petite carte de situation : la province choisie en surbrillance parmi les 47 (projection simple). */
export default function Localisation({
  provinces,
  pcode,
  pcodes,
  couleur = "#2fbf7f",
  largeur = 190,
}: {
  provinces: GeoJSON.FeatureCollection;
  pcode?: string;
  pcodes?: string[];
  couleur?: string;
  largeur?: number;
}) {
  const { chemins, hauteur } = useMemo(() => {
    let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
    for (const f of provinces.features)
      for (const a of anneaux(f.geometry))
        for (const [x, y] of a) {
          x0 = Math.min(x0, x);
          x1 = Math.max(x1, x);
          y0 = Math.min(y0, y);
          y1 = Math.max(y1, y);
        }
    const kx = Math.cos(((y0 + y1) / 2) * (Math.PI / 180));
    const echelle = (largeur - 4) / ((x1 - x0) * kx);
    const h = (y1 - y0) * echelle + 4;
    const chemins = provinces.features.map((f) => ({
      pcode: String(f.properties?.province_pcode),
      d: anneaux(f.geometry)
        .map((a) => "M" + a.map(([x, y]) => `${((x - x0) * kx * echelle + 2).toFixed(1)},${((y1 - y) * echelle + 2).toFixed(1)}`).join("L") + "Z")
        .join(""),
    }));
    return { chemins, hauteur: h };
  }, [provinces, largeur]);

  const choisies = chemins.filter((c) => c.pcode === pcode || (pcodes ?? []).includes(c.pcode));
  const fin = largeur < 120 ? 0.4 : 0.6;
  return (
    <svg className="localisation" width={largeur} height={hauteur} viewBox={`0 0 ${largeur} ${hauteur}`} role="img" aria-label="Situation de la province">
      {chemins.map((c) => (
        <path key={c.pcode} d={c.d} fill="#1e3157" stroke="#3b5480" strokeWidth={fin} />
      ))}
      {choisies.map((c) => (
        <path key={`s-${c.pcode}`} d={c.d} fill={couleur} stroke="#ffffff" strokeWidth={fin * 1.6} />
      ))}
    </svg>
  );
}
