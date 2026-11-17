"use client";

import * as echarts from "echarts";
import { useEffect, useRef } from "react";

export default function Graphique({
  option,
  hauteur = 300,
  surClic,
  libelle,
}: {
  option: object;
  hauteur?: number;
  surClic?: (p: echarts.ECElementEvent) => void;
  libelle?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const instance = useRef<echarts.ECharts | null>(null);
  const clic = useRef(surClic);
  clic.current = surClic;

  useEffect(() => {
    if (!ref.current) return;
    const g = echarts.init(ref.current, undefined, { renderer: "canvas" });
    instance.current = g;
    g.on("click", (p) => clic.current?.(p));
    const observateur = new ResizeObserver(() => g.resize());
    observateur.observe(ref.current);
    return () => {
      observateur.disconnect();
      g.dispose();
      instance.current = null;
    };
  }, []);

  useEffect(() => {
    instance.current?.setOption(
      { textStyle: { fontFamily: "Segoe UI, Inter, system-ui, sans-serif" }, animationDuration: 500, ...option } as echarts.EChartsOption,
      true,
    );
  }, [option]);

  return <div ref={ref} style={{ width: "100%", height: hauteur }} role="img" aria-label={libelle} />;
}
