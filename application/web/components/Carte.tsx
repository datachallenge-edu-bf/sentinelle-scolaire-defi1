"use client";

import maplibregl from "maplibre-gl";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Carte as DonneesCarte } from "@/lib/api";
import { COULEURS_CLASSES } from "@/lib/format";

export interface Couches {
  risque: boolean;
  rupture: boolean;
  limites: boolean;
  scindees: boolean;
}

type Proprietes = Record<string, unknown>;

const LIMITES_BURKINA: [[number, number], [number, number]] = [
  [-5.6, 9.35],
  [2.45, 15.1],
];
const VIDE = "#2b3a55";

/** Motif hachuré des provinces en alerte de rupture, dessiné une fois (aucune tuile ni image externe). */
function hachures(): { width: number; height: number; data: Uint8Array } {
  const taille = 16;
  const toile = document.createElement("canvas");
  toile.width = toile.height = taille;
  const c = toile.getContext("2d")!;
  c.strokeStyle = "rgba(255,255,255,0.85)";
  c.lineWidth = 2.2;
  for (const d of [-taille, 0, taille]) {
    c.beginPath();
    c.moveTo(d, taille);
    c.lineTo(d + taille, 0);
    c.stroke();
  }
  return { width: taille, height: taille, data: new Uint8Array(c.getImageData(0, 0, taille, taille).data) };
}

export default function Carte({
  donnees,
  mode = "provinces",
  couches = { risque: true, rupture: true, limites: true, scindees: false },
  couleursRegions,
  infoProvince,
  infoRegion,
  surClic,
  selection,
  compacte,
  enfants,
  etiquettesProvinces,
}: {
  donnees: DonneesCarte;
  mode?: "provinces" | "regions";
  couches?: Couches;
  couleursRegions?: Record<string, string>;
  infoProvince?: (p: Proprietes) => ReactNode;
  infoRegion?: (nom: string) => ReactNode;
  surClic?: (cle: string) => void;
  selection?: string | null;
  compacte?: boolean;
  enfants?: ReactNode;
  etiquettesProvinces?: Record<string, string>;
}) {
  const conteneur = useRef<HTMLDivElement>(null);
  const carte = useRef<maplibregl.Map | null>(null);
  const etiquettes = useRef<maplibregl.Marker[]>([]);
  const etiquettesP = useRef<Record<string, HTMLDivElement>>({});
  const [zoomee, setZoomee] = useState(false);
  const [prete, setPrete] = useState(false);
  const [bulle, setBulle] = useState<{ x: number; y: number; contenu: ReactNode } | null>(null);
  const rappels = useRef({ infoProvince, infoRegion, surClic });
  rappels.current = { infoProvince, infoRegion, surClic };

  const regionsColorees = (): GeoJSON.FeatureCollection => ({
    ...donnees.regions,
    features: donnees.regions.features.map((f) => ({
      ...f,
      properties: { ...f.properties, couleur: couleursRegions?.[String(f.properties?.region_nom)] ?? VIDE },
    })),
  });

  // Création de la carte (une seule fois).
  useEffect(() => {
    if (!conteneur.current) return;
    const m = new maplibregl.Map({
      container: conteneur.current,
      style: {
        version: 8,
        sources: {},
        layers: [{ id: "fond", type: "background", paint: { "background-color": "rgba(0,0,0,0)" } }],
      },
      bounds: LIMITES_BURKINA,
      fitBoundsOptions: { padding: 24 },
      attributionControl: false,
      // Garde l'image de la carte pour l'impression et l'export PDF.
      canvasContextAttributes: { preserveDrawingBuffer: true },
      dragRotate: false,
      pitchWithRotate: false,
      maxZoom: 10,
      minZoom: 4.5,
    });
    m.touchZoomRotate.disableRotation();
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.addControl(new maplibregl.FullscreenControl(), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 140 }), "bottom-left");
    carte.current = m;

    m.on("load", () => {
      m.addImage("hachures", hachures(), { pixelRatio: 2 });
      m.addSource("provinces", { type: "geojson", data: donnees.provinces, promoteId: "province_pcode" });
      m.addSource("regions", { type: "geojson", data: regionsColorees(), promoteId: "region_nom" });

      m.addLayer({
        id: "regions-remplissage",
        type: "fill",
        source: "regions",
        layout: { visibility: mode === "regions" ? "visible" : "none" },
        paint: {
          "fill-color": ["get", "couleur"],
          "fill-opacity": ["case", ["boolean", ["feature-state", "survol"], false], 1, 0.88],
        },
      });
      m.addLayer({
        id: "provinces-remplissage",
        type: "fill",
        source: "provinces",
        layout: { visibility: mode === "provinces" ? "visible" : "none" },
        paint: {
          "fill-color": [
            "match",
            ["get", "classe"],
            "faible",
            COULEURS_CLASSES.faible,
            "moyen",
            COULEURS_CLASSES.moyen,
            "élevé",
            COULEURS_CLASSES["élevé"],
            VIDE,
          ],
          "fill-opacity": ["case", ["boolean", ["feature-state", "survol"], false], 1, 0.9],
        },
      });
      m.addLayer({
        id: "provinces-rupture",
        type: "fill",
        source: "provinces",
        filter: ["==", ["get", "rupture"], "élevé"],
        layout: { visibility: mode === "provinces" ? "visible" : "none" },
        paint: { "fill-pattern": "hachures", "fill-opacity": 0.75 },
      });
      m.addLayer({
        id: "provinces-contour",
        type: "line",
        source: "provinces",
        paint: { "line-color": "#0a111f", "line-width": 0.9, "line-opacity": 0.9 },
      });
      m.addLayer({
        id: "provinces-scindees",
        type: "line",
        source: "provinces",
        filter: ["==", ["get", "scindee"], true],
        layout: { visibility: "none" },
        paint: { "line-color": "#f8fafc", "line-width": 1.6, "line-dasharray": [2, 1.5] },
      });
      m.addLayer({
        id: "regions-contour",
        type: "line",
        source: "regions",
        paint: { "line-color": "#f1f5f9", "line-width": 1.6, "line-opacity": 0.85 },
      });
      m.addLayer({
        id: "survol",
        type: "line",
        source: mode === "regions" ? "regions" : "provinces",
        paint: {
          "line-color": "#ffffff",
          "line-width": ["case", ["boolean", ["feature-state", "survol"], false], 3, 0],
        },
      });
      m.addLayer({
        id: "selection",
        type: "line",
        source: mode === "regions" ? "regions" : "provinces",
        filter: ["==", ["get", mode === "regions" ? "region_nom" : "province_pcode"], ""],
        paint: { "line-color": "#ffffff", "line-width": 3.2 },
      });

      etiquettes.current = Object.entries(donnees.etiquettes_regions).map(([nom, [x, y]]) => {
        const e = document.createElement("div");
        e.className = "etiquette-region";
        e.textContent = nom;
        return new maplibregl.Marker({ element: e }).setLngLat([x, y]).addTo(m);
      });

      if (mode === "provinces") {
        for (const [pcode, [x, y]] of Object.entries(donnees.etiquettes_provinces)) {
          const e = document.createElement("div");
          e.className = "etiquette-province";
          etiquettesP.current[pcode] = e;
          new maplibregl.Marker({ element: e }).setLngLat([x, y]).addTo(m);
        }
      }
      const suivreZoom = () => setZoomee(m.getZoom() >= 6.7);
      m.on("zoom", suivreZoom);
      suivreZoom();

      const couche = mode === "regions" ? "regions-remplissage" : "provinces-remplissage";
      const source = mode === "regions" ? "regions" : "provinces";
      let survole: string | number | undefined;
      m.on("mousemove", couche, (e) => {
        const f = e.features?.[0];
        if (!f) return;
        if (survole !== undefined) m.setFeatureState({ source, id: survole }, { survol: false });
        survole = f.id;
        if (survole !== undefined) m.setFeatureState({ source, id: survole }, { survol: true });
        m.getCanvas().style.cursor = "pointer";
        const p = f.properties as Proprietes;
        const contenu =
          mode === "regions"
            ? rappels.current.infoRegion?.(String(p.region_nom))
            : rappels.current.infoProvince?.(p);
        setBulle(contenu ? { x: e.point.x, y: e.point.y, contenu } : null);
      });
      m.on("mouseleave", couche, () => {
        if (survole !== undefined) m.setFeatureState({ source, id: survole }, { survol: false });
        survole = undefined;
        m.getCanvas().style.cursor = "";
        setBulle(null);
      });
      m.on("click", couche, (e) => {
        const p = e.features?.[0]?.properties as Proprietes | undefined;
        if (!p) return;
        rappels.current.surClic?.(String(mode === "regions" ? p.region_nom : p.province_pcode));
      });
      setPrete(true);
    });

    return () => {
      etiquettes.current.forEach((e) => e.remove());
      m.remove();
      carte.current = null;
    };
    // La carte est créée une fois ; les données et couches sont mises à jour plus bas.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Nouvelles données (changement de population) ou nouvelles couleurs de régions.
  useEffect(() => {
    const m = carte.current;
    if (!prete || !m) return;
    (m.getSource("provinces") as maplibregl.GeoJSONSource).setData(donnees.provinces);
    (m.getSource("regions") as maplibregl.GeoJSONSource).setData(regionsColorees());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prete, donnees, couleursRegions]);

  // Couches affichées.
  useEffect(() => {
    const m = carte.current;
    if (!prete || !m) return;
    const voir = (id: string, v: boolean) => m.setLayoutProperty(id, "visibility", v ? "visible" : "none");
    if (mode === "provinces") {
      voir("provinces-remplissage", couches.risque);
      voir("provinces-rupture", couches.rupture);
    }
    voir("regions-contour", couches.limites);
    voir("provinces-scindees", couches.scindees);
    etiquettes.current.forEach((e) => (e.getElement().style.display = couches.limites && !zoomee ? "" : "none"));
  }, [prete, couches, mode, zoomee]);

  // Noms et taux des provinces, visibles quand on zoome.
  useEffect(() => {
    if (!prete) return;
    for (const [pcode, e] of Object.entries(etiquettesP.current)) {
      e.textContent = etiquettesProvinces?.[pcode] ?? "";
      e.style.display = zoomee ? "" : "none";
    }
  }, [prete, etiquettesProvinces, zoomee]);

  // Province ou région choisie.
  useEffect(() => {
    const m = carte.current;
    if (!prete || !m) return;
    m.setFilter("selection", ["==", ["get", mode === "regions" ? "region_nom" : "province_pcode"], selection ?? ""]);
  }, [prete, selection, mode]);

  const largeur = conteneur.current?.clientWidth ?? 800;
  return (
    <div className={`carte-conteneur${compacte ? " compacte" : ""}`}>
      <div ref={conteneur} className="carte" aria-label="Carte du Burkina Faso par province" />
      {enfants}
      {bulle ? (
        <div
          className="info-bulle"
          style={{
            left: bulle.x > largeur - 270 ? bulle.x - 250 : bulle.x + 16,
            top: Math.max(8, bulle.y - 20),
          }}
        >
          {bulle.contenu}
        </div>
      ) : null}
    </div>
  );
}
