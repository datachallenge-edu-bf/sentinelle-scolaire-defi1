"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo } from "react";
import Badge from "@/components/Badge";
import BasculePopulation from "@/components/BasculePopulation";
import { Graphique } from "@/components/dynamique";
import { Chargement, Erreur } from "@/components/Etat";
import Localisation from "@/components/Localisation";
import { IconeRapport } from "@/components/Icones";
import { usePopulation } from "@/components/usePopulation";
import { useApi, type Carte as DonneesCarte, type Classe, type Province } from "@/lib/api";
import {
  avecPopulation,
  COULEURS_CLASSES,
  COULEURS_SEXE,
  intervalle,
  LIBELLES_CLASSES,
  nombre,
  pourcent,
} from "@/lib/format";
import { axe, INFO_BULLE, TEXTE, TEXTE_DISCRET, TEXTE_FORT } from "@/lib/theme";

const VERT = "#2fbf7f";

function optionHistorique(p: Province) {
  const histo = p.historique[p.population];
  const proj = p.projections;
  const annees = [...histo.map((h) => h.annee), ...proj.map((x) => x.annee)];
  const dernier = histo[histo.length - 1];
  const nh = histo.length;
  const vide = (k: number) => Array(k).fill(null);

  const observe = histo.map((h) =>
    h.rupture
      ? null
      : {
          value: h.taux,
          itemStyle: h.observe ? { color: VERT } : { color: "#111a2b", borderColor: VERT, borderWidth: 2 },
        },
  );
  const prevu = [...vide(nh - 1), dernier && !dernier.rupture ? dernier.taux : null, ...proj.map((x) => x.taux)];
  const bas = [...vide(nh - 1), dernier && !dernier.rupture ? dernier.taux : null, ...proj.map((x) => x.borne_basse)];
  const largeur = [...vide(nh - 1), dernier && !dernier.rupture ? 0 : null, ...proj.map((x) => x.borne_haute - x.borne_basse)];
  const valeursY = [...histo.filter((h) => !h.rupture).map((h) => h.taux), ...proj.map((x) => x.borne_haute)];
  const maxY = Math.ceil((Math.max(...valeursY) * 1.08) / 5) * 5;

  const ruptures = [...histo.map((h) => (h.rupture ? maxY : null)), ...vide(proj.length)];

  return {
    grid: { left: 20, right: 16, top: 40, bottom: 8, containLabel: true },
    legend: {
      top: 0,
      left: 0,
      itemWidth: 16,
      itemHeight: 10,
      textStyle: { color: TEXTE, fontSize: 12 },
      data: ["Taux observé", "Prévision et projections", "Intervalle à 80 %", "Année de rupture"],
    },
    tooltip: {
      ...INFO_BULLE,
      trigger: "axis",
      formatter: (items: { dataIndex: number }[]) => {
        const k = items[0]?.dataIndex ?? 0;
        if (k < nh) {
          const h = histo[k];
          const nature = h.rupture ? "année de rupture (exclue du modèle)" : h.observe ? "valeur observée" : "valeur reconstituée";
          return `<b>${h.annee}</b><br/>Taux d'abandon : <b>${pourcent(h.taux)}</b><br/><span style="color:${TEXTE_DISCRET}">${nature}</span>`;
        }
        const x = proj[k - nh];
        const nature = x.horizon === 1 ? "prévision" : "projection indicative";
        return `<b>${x.annee}</b> (${nature})<br/>Taux prévu : <b>${pourcent(x.taux)}</b><br/>Intervalle à 80 % : ${intervalle(x.borne_basse, x.borne_haute)}`;
      },
    },
    xAxis: { ...axe(undefined, false), type: "category", boundaryGap: true, data: annees, axisLabel: { color: TEXTE, fontSize: 11.5, interval: 0, rotate: 30 } },
    yAxis: { ...axe(), type: "value", max: maxY, axisLabel: { color: TEXTE, formatter: "{value} %" } },
    series: [
      {
        name: "Année de rupture",
        type: "bar",
        data: ruptures,
        barWidth: "92%",
        silent: true,
        itemStyle: { color: "rgba(139, 92, 246, 0.16)" },
        tooltip: { show: false },
        z: 0,
      },
      {
        name: "Intervalle à 80 %",
        type: "line",
        stack: "ic",
        data: bas,
        lineStyle: { opacity: 0 },
        symbol: "none",
        tooltip: { show: false },
      },
      {
        name: "Intervalle à 80 %",
        type: "line",
        stack: "ic",
        data: largeur,
        lineStyle: { opacity: 0 },
        symbol: "none",
        areaStyle: { color: "rgba(47, 191, 127, 0.18)" },
        itemStyle: { color: "rgba(47, 191, 127, 0.45)" },
      },
      {
        name: "Taux observé",
        type: "line",
        data: [...observe, ...vide(proj.length)],
        itemStyle: { color: VERT },
        lineStyle: { width: 2, color: VERT },
        symbolSize: 8,
        connectNulls: false,
      },
      {
        name: "Prévision et projections",
        type: "line",
        data: prevu,
        itemStyle: { color: VERT },
        lineStyle: { width: 2, type: "dashed", color: VERT },
        symbolSize: (_: unknown, x: { dataIndex: number }) => (x.dataIndex === nh ? 12 : 8),
        label: {
          show: true,
          position: "top",
          color: TEXTE_FORT,
          fontWeight: 600,
          formatter: (x: { dataIndex: number; value: number }) => (x.dataIndex >= nh ? pourcent(x.value) : ""),
        },
      },
    ],
  };
}

function optionCascade(p: Province) {
  const c = p.cascade;
  const lignes = [
    ...c.contributions.map((x) => ({ nom: x.libelle, valeur: x.contribution })),
    { nom: "Autres caractéristiques", valeur: c.autres },
  ];
  const noms = ["Moyenne des provinces", ...lignes.map((l) => l.nom), "Niveau expliqué de la province"];
  const base: (number | null)[] = [0];
  const barres: { value: number; itemStyle: object }[] = [{ value: c.base, itemStyle: { color: "#64748b", borderRadius: 4 } }];
  let cumul = c.base;
  for (const l of lignes) {
    const debut = l.valeur >= 0 ? cumul : cumul + l.valeur;
    base.push(debut);
    barres.push({ value: Math.abs(l.valeur), itemStyle: { color: l.valeur >= 0 ? COULEURS_CLASSES["élevé"] : COULEURS_CLASSES.faible, borderRadius: 3 } });
    cumul += l.valeur;
  }
  base.push(0);
  barres.push({ value: c.niveau_explique, itemStyle: { color: VERT, borderRadius: 4 } });
  const signes = [null, ...lignes.map((l) => l.valeur), null];

  return {
    grid: { left: 8, right: 56, top: 4, bottom: 4, containLabel: true },
    tooltip: {
      ...INFO_BULLE,
      trigger: "item",
      formatter: (x: { dataIndex: number }) => {
        const k = x.dataIndex;
        if (k === 0) return `Moyenne des provinces : <b>${pourcent(c.base)}</b>`;
        if (k === noms.length - 1) return `Niveau expliqué : <b>${pourcent(c.niveau_explique)}</b>`;
        const v = signes[k]!;
        const detail = c.contributions[k - 1];
        const valeur = detail && detail.valeur !== null ? `<br/>Valeur de la province : ${nombre(detail.valeur, detail.valeur < 1.5 ? 3 : 1)}` : "";
        return `<b>${noms[k]}</b><br/>${v >= 0 ? "+" : ""}${nombre(v, 2)} point${valeur}`;
      },
    },
    xAxis: { type: "value", show: false },
    yAxis: {
      type: "category",
      inverse: true,
      data: noms,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: TEXTE_FORT,
        fontSize: 12,
        width: 190,
        overflow: "break",
        fontWeight: (v: string) => (v === noms[0] || v === noms[noms.length - 1] ? 700 : 400),
      },
    },
    series: [
      { type: "bar", stack: "c", data: base, itemStyle: { color: "transparent" }, tooltip: { show: false }, barWidth: 16 },
      {
        type: "bar",
        stack: "c",
        data: barres,
        barWidth: 16,
        label: {
          show: true,
          position: "right",
          color: TEXTE_FORT,
          fontSize: 12,
          formatter: (x: { dataIndex: number }) => {
            const k = x.dataIndex;
            if (k === 0) return pourcent(c.base);
            if (k === noms.length - 1) return pourcent(c.niveau_explique);
            const v = signes[k]!;
            return `${v >= 0 ? "+" : "−"}${nombre(Math.abs(v))}`;
          },
        },
      },
    ],
  };
}

function optionJauge(p: Province) {
  const [s1, s2] = p.rupture.seuils;
  return {
    series: [
      {
        type: "gauge",
        min: 0,
        max: 1,
        startAngle: 200,
        endAngle: -20,
        radius: "100%",
        center: ["50%", "62%"],
        splitNumber: 2,
        axisLine: {
          lineStyle: {
            width: 14,
            color: [
              [s1, COULEURS_CLASSES.faible],
              [s2, COULEURS_CLASSES.moyen],
              [1, COULEURS_CLASSES["élevé"]],
            ],
          },
        },
        pointer: { length: "62%", width: 5, itemStyle: { color: "#e2e8f0" } },
        anchor: { show: true, size: 10, itemStyle: { color: "#e2e8f0" } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { color: TEXTE, distance: -38, fontSize: 11.5, formatter: (v: number) => nombre(v, 1) },
        detail: { valueAnimation: true, offsetCenter: [0, "34%"], color: TEXTE_FORT, fontSize: 26, fontWeight: 700, formatter: (v: number) => nombre(v, 2) },
        data: [{ value: p.rupture.score }],
      },
    ],
  };
}

export default function FicheProvince() {
  const { pcode } = useParams<{ pcode: string }>();
  const [population, setPopulation] = usePopulation();
  const { donnees: p, erreur } = useApi<Province>(`/api/province/${pcode}?population=${population}`);
  const { donnees: carte } = useApi<DonneesCarte>("/api/carte");

  const histo = useMemo(() => (p ? optionHistorique(p) : null), [p]);
  const cascade = useMemo(() => (p ? optionCascade(p) : null), [p]);
  const jauge = useMemo(() => (p ? optionJauge(p) : null), [p]);

  if (erreur) return <Erreur message={erreur} />;
  if (!p) return <Chargement />;
  const r = p.prevision;
  const id = p.identite;
  const maxSexe = Math.max(...Object.values(p.par_sexe).map((s) => s!.borne_haute), 1);
  const ecart = r.taux_actuel === null ? null : r.taux - r.taux_actuel;

  return (
    <>
      <header className="entete compacte">
        <div>
          <nav className="fil-ariane" aria-label="Fil d'Ariane">
            <Link href={avecPopulation("/", population)}>Vue nationale</Link>
            <span>›</span>
            <Link href={avecPopulation("/regions", population)}>Région {id.region}</Link>
          </nav>
          <h1>
            {id.province} <em>· région {id.region}</em>
          </h1>
        </div>
        <div className="commandes">
          <BasculePopulation valeur={population} changer={setPopulation} />
          <a className="bouton" href={`/api/rapport/province/${id.pcode}?population=${population}`}>
            <IconeRapport taille={18} /> Rapport PDF
          </a>
        </div>
      </header>

      <section className="tuiles" aria-label={`Indicateurs de ${id.province}`}>
        <div className="tuile" style={{ "--teinte": "#64748b" } as React.CSSProperties}>
          <div className="tuile-valeur">{pourcent(r.taux_actuel)}</div>
          <div className="tuile-libelle">Observé {p.annee_des_variables}</div>
        </div>
        <div className="tuile" style={{ "--teinte": COULEURS_CLASSES[r.classe] } as React.CSSProperties}>
          <div className="tuile-valeur">
            {pourcent(r.taux)}{" "}
            {ecart !== null ? (
              <small style={{ color: ecart > 0 ? "#ff8fa3" : "#6ee7b7" }}>
                {ecart > 0 ? "▲" : "▼"} {nombre(Math.abs(ecart))}
              </small>
            ) : null}
          </div>
          <div className="tuile-libelle">Prévision 2025-2026</div>
          <div className="tuile-detail">intervalle à 80 % {intervalle(r.borne_basse, r.borne_haute)}</div>
        </div>
        <div className="tuile" style={{ "--teinte": COULEURS_CLASSES[r.classe] } as React.CSSProperties}>
          <div className="tuile-valeur">
            <Badge classe={r.classe} grand texte={`Risque ${LIBELLES_CLASSES[r.classe].toLowerCase()}`} />
          </div>
          <div className="tuile-libelle">
            {id.rang}
            <sup>{id.rang === 1 ? "er" : "e"}</sup> sur {id.provinces} provinces
          </div>
        </div>
        <div className="tuile" style={{ "--teinte": COULEURS_CLASSES[p.rupture.classe] } as React.CSSProperties}>
          <div className="tuile-valeur">
            {nombre(p.rupture.score, 2)} <small>/ 1</small>
          </div>
          <div className="tuile-libelle">Score de rupture : {LIBELLES_CLASSES[p.rupture.classe].toLowerCase()}</div>
        </div>
        <div className="tuile" style={{ "--teinte": VERT } as React.CSSProperties}>
          <div className="tuile-valeur">
            {pourcent(p.cascade.niveau_explique)}
          </div>
          <div className="tuile-libelle">Niveau attendu d&apos;après ses caractéristiques</div>
          <div className="tuile-detail">moyenne des provinces {pourcent(p.cascade.base)}</div>
        </div>
        <div className="tuile tuile-carte" style={{ "--teinte": VERT } as React.CSSProperties}>
          <div className="tuile-libelle">
            {id.scindee ? `Créée en 2025 (ex-${id.ancienne_province})` : "Situation"}
          </div>
          {carte ? <Localisation provinces={carte.provinces} pcode={id.pcode} largeur={110} /> : null}
        </div>
      </section>

      <div className="grille g-fiche">
        <section className="panneau">
          <div className="panneau-titre">
            <h2>{id.province} : taux d&apos;abandon de 2016-2017 à 2027-2028</h2>
            <p>Points creux : valeurs reconstituées · bandes violettes : années de rupture.</p>
          </div>
          {histo ? <Graphique option={histo} hauteur={430} libelle={`Évolution du taux d'abandon, ${id.province}`} /> : null}
        </section>

        <section className="panneau">
          <div className="panneau-titre">
            <h2>{id.province} : facteurs du niveau habituel (SHAP)</h2>
            <p>En rouge, ce qui élève le niveau ; en vert, ce qui l&apos;abaisse (points de taux).</p>
          </div>
          {cascade ? <Graphique option={cascade} hauteur={430} libelle={`Facteurs SHAP, ${id.province}`} /> : null}
        </section>

        <div className="colonne">
          <section className="panneau">
            <div className="panneau-titre">
              <h2>{id.province} : filles et garçons, 2025-2026</h2>
            </div>
            <div className="barres-sexe">
              {(["F", "G"] as const).map((s) => {
                const x = p.par_sexe[s];
                if (!x) return null;
                return (
                  <div key={s} title={`Intervalle à 80 % ${intervalle(x.borne_basse, x.borne_haute)}`}>
                    <div className="barre-sexe">
                      <span>{s === "F" ? "Filles" : "Garçons"}</span>
                      <div className="piste">
                        <div style={{ width: `${(100 * x.taux) / maxSexe}%`, background: COULEURS_SEXE[s] }} />
                      </div>
                      <span className="valeur-num">{pourcent(x.taux)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="panneau" style={{ flex: 1 }}>
            <div className="panneau-titre">
              <h2>{id.province} : risque de rupture</h2>
              <p>Variation des effectifs de plus de 30 % l&apos;an prochain.</p>
            </div>
            {jauge ? <Graphique option={jauge} hauteur={160} libelle={`Score de rupture : ${nombre(p.rupture.score, 2)}`} /> : null}
            <ul className="signaux">
              {p.rupture.signaux.slice(0, 3).map((s) => (
                <li key={s.signal}>
                  <span>{s.signal}</span>
                  <span style={{ color: s.contribution > 0 ? "#ff8fa3" : "#6ee7b7" }}>{s.contribution > 0 ? "▲ augmente" : "▼ réduit"}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}
