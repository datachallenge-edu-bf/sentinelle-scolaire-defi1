"use client";

import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import Badge from "@/components/Badge";
import BasculePopulation from "@/components/BasculePopulation";
import type { Couches } from "@/components/Carte";
import CurseurAnnees from "@/components/CurseurAnnees";
import { Carte, Graphique } from "@/components/dynamique";
import { Chargement, Erreur } from "@/components/Etat";
import Localisation from "@/components/Localisation";
import { Bande47, Comparaison, Courbe } from "@/components/MiniVisuels";
import { IconeRapport, IconeTableur } from "@/components/Icones";
import TiroirAlertes from "@/components/TiroirAlertes";
import { usePopulation } from "@/components/usePopulation";
import { useApi, type Carte as DonneesCarte, type Classe, type National, type ProvinceNationale } from "@/lib/api";
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

const VIOLET = "#8b5cf6";
const CLASSES: Classe[] = ["élevé", "moyen", "faible"];

type Ligne = { p: ProvinceNationale; rang: number };

function optionClassement(lignes: Ligne[], k: number, defilement: boolean) {
  const etiquette = (l: Ligne) => {
    const s = l.p.serie[k];
    return s.bas !== null && s.haut !== null ? `${pourcent(s.taux)}  ${intervalle(s.bas, s.haut)}` : pourcent(s.taux);
  };
  const max = Math.max(...lignes.map((l) => l.p.serie[k].haut ?? l.p.serie[k].taux ?? 0), 1);
  return {
    grid: { left: 4, right: defilement ? 132 : 118, top: 2, bottom: 2, containLabel: true },
    tooltip: {
      ...INFO_BULLE,
      trigger: "item",
      formatter: (x: { dataIndex: number }) => {
        const l = lignes[x.dataIndex];
        const s = l.p.serie[k];
        const ic = s.bas !== null && s.haut !== null ? `<br/>Intervalle à 80 % : ${intervalle(s.bas, s.haut)}` : "";
        return `<b>${l.rang}. ${l.p.province}</b> (${l.p.region})<br/>${s.annee} : <b>${pourcent(s.taux)}</b>${ic}`;
      },
    },
    xAxis: { type: "value", show: false, max: max * 0.62 },
    yAxis: {
      type: "category",
      inverse: true,
      data: lignes.map((l) => `${l.rang}. ${l.p.province}`),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: TEXTE_FORT, fontSize: 12, width: 112, overflow: "truncate" },
    },
    dataZoom: defilement
      ? [
          { type: "inside", yAxisIndex: 0, startValue: 0, endValue: 9, zoomLock: true, moveOnMouseWheel: true, zoomOnMouseWheel: false },
          { type: "slider", yAxisIndex: 0, startValue: 0, endValue: 9, width: 6, right: 4, zoomLock: true, showDetail: false, brushSelect: false, borderColor: "transparent", fillerColor: "rgba(130,147,173,.45)", handleSize: 0, backgroundColor: "rgba(130,147,173,.12)", dataBackground: { lineStyle: { opacity: 0 }, areaStyle: { opacity: 0 } } },
        ]
      : undefined,
    series: [
      {
        type: "bar",
        barWidth: 12,
        data: lignes.map((l) => ({
          value: l.p.serie[k].taux,
          itemStyle: { color: COULEURS_CLASSES[l.p.serie[k].classe ?? "faible"], borderRadius: [0, 4, 4, 0] },
        })),
        label: { show: true, position: "right", color: TEXTE, fontSize: 11.5, formatter: (x: { dataIndex: number }) => etiquette(lignes[x.dataIndex]) },
      },
    ],
  };
}

export default function VueNationale() {
  const [population, setPopulation] = usePopulation();
  const routeur = useRouter();
  const { donnees: n, erreur } = useApi<National>(`/api/national?population=${population}`);
  const { donnees: carte } = useApi<DonneesCarte>("/api/carte");
  const [k, setK] = useState(1);
  const [couches, setCouches] = useState<Couches>({ risque: true, rupture: true, limites: true, scindees: false });
  const ouvrir = useCallback((pcode: string) => routeur.push(avecPopulation(`/province/${pcode}`, population)), [routeur, population]);
  const changerAnnee = useCallback((x: number) => setK(x), []);

  const tri = useMemo<Ligne[]>(() => {
    if (!n) return [];
    return [...n.provinces]
      .filter((p) => p.serie[k].taux !== null)
      .sort((a, b) => (b.serie[k].taux ?? 0) - (a.serie[k].taux ?? 0))
      .map((p, i) => ({ p, rang: i + 1 }));
  }, [n, k]);

  const carteAnnee = useMemo<DonneesCarte | null>(() => {
    if (!carte || !n) return null;
    const parCode = Object.fromEntries(n.provinces.map((p) => [p.pcode, p]));
    return {
      ...carte,
      provinces: {
        ...carte.provinces,
        features: carte.provinces.features.map((f) => {
          const p = parCode[String(f.properties?.province_pcode)];
          const s = p?.serie[k];
          return {
            ...f,
            properties: {
              ...f.properties,
              classe: s?.classe ?? "",
              taux: s?.taux ?? null,
              bas: s?.bas ?? null,
              haut: s?.haut ?? null,
              avant: p?.serie[0].taux ?? null,
              rupture: k >= 1 ? p?.rupture : "",
              score_rupture: p?.score_rupture,
              scindee: p?.scindee ?? false,
              ancienne_province: p?.ancienne_province ?? "",
            },
          };
        }),
      },
    };
  }, [carte, n, k]);

  const etiquettes = useMemo(
    () => Object.fromEntries((n?.provinces ?? []).map((p) => [p.pcode, `${p.province}\n${pourcent(p.serie[k].taux)}`])),
    [n, k],
  );

  const optionNuage = useMemo(() => {
    if (!n) return null;
    const vars = n.nuage_shap.variables;
    const points = n.nuage_shap.points;
    // Placement en essaim (comme le « beeswarm » de SHAP) : sur chaque ligne, un point est posé au plus près de
    // l'axe sans chevaucher les points déjà placés ; la ligne s'épaissit là où les provinces se ressemblent.
    const xs = points.map((p) => p.shap);
    const xmin = Math.min(...xs);
    const xmax = Math.max(...xs);
    const largeur = 560;
    const hauteurLigne = 340 / vars.length;
    const rayon = 7.4;
    const enEssaim: [number, number, number, string, number | null, number][] = [];
    vars.forEach((_, v) => {
      const ligne = points.filter((p) => p.v === v).sort((a, b) => a.shap - b.shap);
      const poses: { x: number; y: number }[] = [];
      for (const p of ligne) {
        const x = ((p.shap - xmin) / (xmax - xmin || 1)) * largeur;
        let y = 0;
        for (let k = 0; k < 200; k++) {
          const essai = (k % 2 === 0 ? 1 : -1) * Math.ceil(k / 2) * (rayon / 2.2);
          if (poses.every((q) => Math.hypot(q.x - x, q.y - essai) >= rayon)) {
            y = essai;
            break;
          }
        }
        poses.push({ x, y });
        const decalage = Math.max(-0.46, Math.min(0.46, y / hauteurLigne));
        enEssaim.push([p.shap, v + decalage, p.rang ?? 0.5, p.province, p.valeur, v]);
      }
    });
    return {
      grid: { left: 6, right: 70, top: 6, bottom: 34, containLabel: true },
      tooltip: {
        ...INFO_BULLE,
        trigger: "item",
        formatter: (x: { data: [number, number, number, string, number | null, number] }) => {
          const [shap, , , province, valeur, v] = x.data;
          const val = valeur === null ? "n.d." : nombre(valeur, Math.abs(valeur) < 1.5 ? 3 : 1);
          return `<b>${province}</b><br/>${vars[v].libelle} : ${val}<br/>Valeur SHAP : <b>${shap >= 0 ? "+" : "−"}${nombre(Math.abs(shap), 2)} point</b>`;
        },
      },
      xAxis: {
        ...axe("Valeur SHAP (effet sur le niveau d'abandon, en points)"),
        type: "value",
        nameLocation: "middle",
        nameGap: 24,
        splitLine: { show: false },
        axisLabel: { color: TEXTE, formatter: (v: number) => (v > 0 ? `+${v}` : `${v}`) },
      },
      yAxis: [
        {
          type: "category",
          inverse: true,
          data: vars.map((x) => x.libelle),
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: true, lineStyle: { color: "rgba(130,147,173,.07)" } },
          axisLabel: { color: TEXTE_FORT, fontSize: 11.5, width: 170, overflow: "truncate" },
        },
        { type: "value", inverse: true, min: -0.5, max: vars.length - 0.5, show: false },
      ],
      visualMap: {
        type: "continuous",
        dimension: 2,
        min: 0,
        max: 1,
        orient: "vertical",
        right: 4,
        top: "middle",
        itemWidth: 9,
        itemHeight: 200,
        text: ["Élevée", "Faible"],
        textGap: 6,
        textStyle: { color: TEXTE_DISCRET, fontSize: 11 },
        calculable: false,
        inRange: { color: ["#1e88e5", "#7c4dff", "#ff0d57"] },
      },
      series: [
        {
          type: "scatter",
          yAxisIndex: 1,
          symbolSize: 7.5,
          itemStyle: { opacity: 0.95 },
          data: enEssaim,
          markLine: { silent: true, symbol: "none", data: [{ xAxis: 0 }], lineStyle: { color: "#94a3b8", type: "solid", width: 1 }, label: { show: false } },
        },
      ],
    };
  }, [n]);

  const optionSexe = useMemo(() => {
    if (!n) return null;
    const regions = n.sexe_par_region[k];
    return {
      grid: { left: 4, right: 6, top: 28, bottom: 2, containLabel: true },
      legend: { top: 0, right: 0, itemWidth: 11, itemHeight: 11, textStyle: { color: TEXTE }, data: ["Filles", "Garçons"] },
      tooltip: { ...INFO_BULLE, trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: number) => pourcent(v) },
      xAxis: { ...axe(undefined, false), type: "category", data: regions.map((r) => r.region), axisLabel: { color: TEXTE, fontSize: 11, rotate: 40, interval: 0 } },
      yAxis: { ...axe(), type: "value", axisLabel: { color: TEXTE, formatter: "{value} %" } },
      series: [
        { name: "Filles", type: "bar", barGap: "10%", barMaxWidth: 10, itemStyle: { color: COULEURS_SEXE.F, borderRadius: [3, 3, 0, 0] }, data: regions.map((r) => r.filles) },
        { name: "Garçons", type: "bar", barMaxWidth: 10, itemStyle: { color: COULEURS_SEXE.G, borderRadius: [3, 3, 0, 0] }, data: regions.map((r) => r.garcons) },
      ],
    };
  }, [n, k]);

  const optionResistantes = useMemo(() => {
    if (!n) return null;
    const r = n.resistantes;
    return {
      grid: { left: 4, right: 48, top: 26, bottom: 2, containLabel: true },
      legend: {
        top: 0,
        left: 0,
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: TEXTE, fontSize: 11.5 },
        data: [{ name: "Niveau observé", icon: "circle" }, { name: "Niveau attendu", icon: "circle" }],
      },
      tooltip: {
        ...INFO_BULLE,
        trigger: "axis",
        axisPointer: { type: "none" },
        formatter: (items: { dataIndex: number }[]) => {
          const x = r[items[0].dataIndex];
          return `<b>${x.province}</b> (${x.region})<br/>Niveau habituel observé : <b>${pourcent(x.observe)}</b><br/>Attendu d'après ses caractéristiques : ${pourcent(x.attendu)}<br/>Écart : −${nombre(Math.abs(x.ecart))} points`;
        },
      },
      xAxis: { ...axe(), type: "value", axisLabel: { color: TEXTE, formatter: "{value} %" } },
      yAxis: { type: "category", inverse: true, data: r.map((x) => x.province), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: TEXTE_FORT, fontSize: 12 } },
      series: [
        { type: "bar", stack: "e", data: r.map((x) => x.observe), itemStyle: { color: "transparent" }, barWidth: 3, silent: true },
        { type: "bar", stack: "e", data: r.map((x) => x.attendu - x.observe), itemStyle: { color: "#3a4a66" }, barWidth: 3, silent: true },
        { name: "Niveau attendu", type: "scatter", symbolSize: 11, itemStyle: { color: "#8a94a6" }, data: r.map((x) => x.attendu) },
        {
          name: "Niveau observé",
          type: "scatter",
          symbolSize: 11,
          itemStyle: { color: "#2fbf7f" },
          data: r.map((x) => x.observe),
          label: { show: true, position: "left", color: "#6ee7b7", fontSize: 11, formatter: (x: { dataIndex: number }) => `−${nombre(Math.abs(r[x.dataIndex].ecart))}` },
        },
      ],
    };
  }, [n]);

  const optionRepartition = useMemo(() => {
    if (!n) return null;
    const compte = (j: number, c: Classe) => n.provinces.filter((p) => p.serie[j].classe === c).length;
    return {
      grid: { left: 4, right: 4, top: 26, bottom: 2, containLabel: true },
      legend: { top: 0, left: 0, itemWidth: 10, itemHeight: 10, textStyle: { color: TEXTE, fontSize: 11.5 }, data: CLASSES.map((c) => LIBELLES_CLASSES[c]) },
      tooltip: { ...INFO_BULLE, trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: number) => `${v} provinces` },
      xAxis: {
        ...axe(undefined, false),
        type: "category",
        data: n.annees,
        axisLabel: { color: TEXTE, fontSize: 11, formatter: (v: string, i: number) => (i === k ? `{a|${v}}` : v), rich: { a: { color: TEXTE_FORT, fontWeight: 700, fontSize: 11 } } },
      },
      yAxis: { ...axe(), type: "value", max: n.provinces.length, interval: 10 },
      series: CLASSES.slice()
        .reverse()
        .map((c) => ({
          name: LIBELLES_CLASSES[c],
          type: "bar",
          stack: "r",
          itemStyle: { color: COULEURS_CLASSES[c] },
          barWidth: "56%",
          data: n.annees.map((_, j) => ({ value: compte(j, c), itemStyle: { color: COULEURS_CLASSES[c], opacity: j === k ? 1 : 0.42 } })),
          label: { show: true, color: "#fff", fontSize: 11, fontWeight: 600, formatter: (x: { value: number }) => (x.value ? x.value : "") },
        })),
    };
  }, [n, k]);

  const premiers = useMemo(() => (tri.length ? optionClassement(tri.slice(0, 10), k, false) : null), [tri, k]);
  const seconds = useMemo(() => (tri.length ? optionClassement(tri.slice(10, 20), k, false) : null), [tri, k]);
  const autres = useMemo(() => (tri.length ? optionClassement(tri.slice(20), k, true) : null), [tri, k]);

  if (erreur) return <Erreur message={erreur} />;
  if (!n) return <Chargement />;

  const total = n.provinces.length;
  const compte = (c: Classe) => n.provinces.filter((p) => p.serie[k].classe === c).length;
  const ruptures = n.provinces.filter((p) => p.rupture === "élevé");
  const tete = tri[0]?.p;
  const annee = n.annees[k];

  return (
    <>
      <header className="entete compacte">
        <h1>
          Vue nationale <em>· décrochage au primaire</em>
        </h1>
        <div className="commandes">
          <BasculePopulation valeur={population} changer={setPopulation} />
          <CurseurAnnees annees={n.annees} valeur={k} changer={changerAnnee} />
          <TiroirAlertes alertes={n.alertes} population={population} />
          <a
            className="bouton secondaire"
            href={`/api/telechargement/previsions?population=${population}`}
            title="Base des prévisions 2025-2028 (CSV pour Excel) : taux, intervalles, classes, abandons estimés"
          >
            <IconeTableur taille={18} /> Données
          </a>
          <a className="bouton" href={`/api/rapport/national?population=${population}`} title="Rapport national à télécharger">
            <IconeRapport taille={18} /> Rapport
          </a>
        </div>
      </header>

      <section className="tuiles" aria-label="Indicateurs clés">
        {n.pays?.[k] ? (
          <div className="tuile tuile-pays" style={{ "--teinte": "#fcd116" } as React.CSSProperties} title="Moyenne des 47 provinces pondérée par leurs effectifs du primaire de 2024-2025">
            <div className="tuile-valeur">{pourcent(n.pays[k].taux)}</div>
            <div className="tuile-libelle">
              <b>Burkina Faso</b> · {n.annees[k]}
            </div>
            <div className="note" style={{ marginTop: 4 }}>
              {n.pays[k].abandons != null
                ? `≈ ${nombre(n.pays[k].abandons! / 1000, 0)} 000 élèves${k > 0 ? " (prévision)" : ""}`
                : k > 0 ? "prévision" : "observé"}
            </div>
          </div>
        ) : null}
        {CLASSES.map((c) => (
          <div key={c} className="tuile" style={{ "--teinte": COULEURS_CLASSES[c] } as React.CSSProperties} title={c === "élevé" ? `Taux ≥ ${nombre(n.seuils.eleve)} %` : c === "moyen" ? `Taux entre ${nombre(n.seuils.moyen)} et ${nombre(n.seuils.eleve)} %` : `Taux < ${nombre(n.seuils.moyen)} %`}>
            <div className="tuile-valeur">
              {compte(c)} <small>/ {total}</small>
            </div>
            <div className="tuile-libelle">Risque {LIBELLES_CLASSES[c].toLowerCase()}</div>
            <Bande47 total={total} compte={compte(c)} couleur={COULEURS_CLASSES[c]} />
          </div>
        ))}
        <div className="tuile tuile-carte" style={{ "--teinte": VIOLET } as React.CSSProperties} title="Variation des effectifs de plus de 30 % attendue l'an prochain">
          <div>
            <div className="tuile-valeur">{ruptures.length}</div>
            <div className="tuile-libelle">Alertes de rupture</div>
          </div>
          {carte ? <Localisation provinces={carte.provinces} pcodes={ruptures.map((p) => p.pcode)} couleur={VIOLET} largeur={96} /> : null}
        </div>
        {tete ? (
          <div className="tuile" style={{ "--teinte": COULEURS_CLASSES[tete.serie[k].classe ?? "élevé"] } as React.CSSProperties} title={`${tete.province}, ${tete.region}`}>
            <div className="tuile-valeur">{pourcent(tete.serie[k].taux)}</div>
            <div className="tuile-libelle">
              Taux le plus élevé : <b>{tete.province}</b>
            </div>
            <Courbe historique={tete.historique} prevision={tete.serie.slice(1).map((s) => s.taux ?? 0)} couleur={COULEURS_CLASSES[tete.serie[k].classe ?? "élevé"]} />
          </div>
        ) : null}
        <div className="tuile" style={{ "--teinte": "#0ea5e9" } as React.CSSProperties} title="Écart moyen absolu sur l'année 2024-2025, jamais vue par les modèles">
          <div className="tuile-valeur">
            {nombre(n.erreurs.sentinelle)} <small>points</small>
          </div>
          <div className="tuile-libelle">Erreur au test final</div>
          <Comparaison nous={n.erreurs.sentinelle} naif={n.erreurs.annee_precedente} />
        </div>
      </section>

      <div className="grille g-carte">
        <section className="panneau panneau-carte">
          <div className="panneau-titre">
            <h2>
              Burkina Faso · {annee} <span className="etiquette-nature">{k === 0 ? "observé" : "prévision"}</span>
            </h2>
            <p>Zoomez pour lire le nom et le taux de chaque province ; cliquez pour ouvrir sa fiche.</p>
          </div>
          {carteAnnee ? (
            <Carte
              donnees={carteAnnee}
              couches={couches}
              surClic={ouvrir}
              etiquettesProvinces={etiquettes}
              infoProvince={(p) => (
                <>
                  <strong>{String(p.province_nom)}</strong> <span>· {String(p.region_nom)}</span>
                  <div className="ligne">
                    {annee} <b>{pourcent(p.taux as number)}</b>
                  </div>
                  {p.bas !== null && p.bas !== undefined ? (
                    <div className="ligne">
                      Intervalle à 80 % <b>{intervalle(Number(p.bas), Number(p.haut))}</b>
                    </div>
                  ) : null}
                  {k > 0 ? (
                    <div className="ligne">
                      Observé {n.annees[0]} <b>{pourcent(p.avant as number)}</b>
                    </div>
                  ) : null}
                  <div className="ligne">
                    Classe {p.classe ? <Badge classe={p.classe as Classe} /> : "n.d."}
                  </div>
                  <div className="ligne">
                    Alerte de rupture <Badge classe={(p.score_rupture as number) >= 0.6 ? "élevé" : (p.score_rupture as number) >= 0.3 ? "moyen" : "faible"} />
                  </div>
                </>
              )}
              enfants={
                <>
                  <div className="couches ne-pas-imprimer">
                    {(
                      [
                        ["risque", "Classes de risque"],
                        ["rupture", "Alertes de rupture"],
                        ["limites", "Régions"],
                        ["scindees", "Provinces créées en 2025"],
                      ] as [keyof Couches, string][]
                    ).map(([cle, texte]) => (
                      <label key={cle}>
                        <input type="checkbox" checked={couches[cle]} onChange={(e) => setCouches({ ...couches, [cle]: e.target.checked })} />
                        {texte}
                      </label>
                    ))}
                  </div>
                  <div className="legende">
                    {(["faible", "moyen", "élevé"] as Classe[]).map((c) => (
                      <div key={c} className="legende-ligne">
                        <span className="pastille" style={{ background: COULEURS_CLASSES[c] }} />
                        {LIBELLES_CLASSES[c]}
                      </div>
                    ))}
                    {k > 0 ? (
                      <div className="legende-ligne">
                        <span className="pastille hachuree" /> Rupture
                      </div>
                    ) : null}
                  </div>
                </>
              }
            />
          ) : (
            <div className="carte-conteneur" />
          )}
        </section>

        <section className="panneau">
          <div className="panneau-titre">
            <h2>Ce qui pousse le risque vers le haut ou le bas (SHAP)</h2>
            <p>Un point par province · à droite du trait, la caractéristique élève le niveau d&apos;abandon · couleur : valeur de la variable.</p>
          </div>
          {optionNuage ? <Graphique option={optionNuage} hauteur={410} libelle="Nuage des valeurs SHAP par province" /> : null}
        </section>
      </div>

      <div className="grille grille-trois" style={{ marginTop: 12 }}>
        {(
          [
            ["Rangs 1 à 10", premiers],
            ["Rangs 11 à 20", seconds],
            [`Rangs 21 à ${tri.length}`, autres],
          ] as [string, object | null][]
        ).map(([titre, option], i) => (
          <section key={titre} className="panneau">
            <div className="panneau-titre">
              <h2>
                {titre} <span className="etiquette-nature">{annee}</span>
              </h2>
            </div>
            {option ? (
              <Graphique option={option} hauteur={262} libelle={`${titre}, ${annee}`} surClic={(x) => ouvrir(tri[i * 10 + x.dataIndex].p.pcode)} />
            ) : null}
          </section>
        ))}
      </div>

      <div className="grille grille-trois" style={{ marginTop: 12 }}>
        <section className="panneau">
          <div className="panneau-titre">
            <h2>
              Filles et garçons par région <span className="etiquette-nature">{annee}</span>
            </h2>
          </div>
          {optionSexe ? <Graphique option={optionSexe} hauteur={226} libelle="Taux des filles et des garçons par région" /> : null}
        </section>
        <section className="panneau">
          <div className="panneau-titre">
            <h2>Provinces qui résistent</h2>
            <p>Niveau habituel nettement sous celui attendu d&apos;après leurs caractéristiques : des pratiques à étudier.</p>
          </div>
          {optionResistantes ? (
            <Graphique option={optionResistantes} hauteur={196} libelle="Provinces qui résistent" surClic={(x) => ouvrir(n.resistantes[x.dataIndex].pcode)} />
          ) : null}
        </section>
        <section className="panneau">
          <div className="panneau-titre">
            <h2>Provinces par classe, d&apos;une année à l&apos;autre</h2>
          </div>
          {optionRepartition ? (
            <Graphique option={optionRepartition} hauteur={226} libelle="Nombre de provinces par classe et par année" surClic={(x) => setK(x.dataIndex)} />
          ) : null}
        </section>
      </div>
    </>
  );
}
