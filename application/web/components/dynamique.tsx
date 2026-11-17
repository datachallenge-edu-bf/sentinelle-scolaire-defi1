"use client";

import dynamic from "next/dynamic";

/** MapLibre et ECharts dessinent dans le navigateur : pas de rendu côté serveur. */
export const Carte = dynamic(() => import("./Carte"), {
  ssr: false,
  loading: () => <div className="carte-conteneur" />,
});

export const Graphique = dynamic(() => import("./Graphique"), { ssr: false });
