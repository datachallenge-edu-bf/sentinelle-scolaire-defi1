"use client";

import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import Badge from "@/components/Badge";
import BasculePopulation from "@/components/BasculePopulation";
import CurseurAnnees from "@/components/CurseurAnnees";
import { Carte, Graphique } from "@/components/dynamique";
import { Chargement, Erreur } from "@/components/Etat";
import { IconeRapport, IconeTableur } from "@/components/Icones";
import TiroirAlertes from "@/components/TiroirAlertes";
import { usePopulation } from "@/components/usePopulation";
import { useApi, type Carte as DonneesCarte, type Classe, type National, type ProvinceNationale } from "@/lib/api";
import { avecPopulation, classeDe, COULEURS_CLASSES, intervalle, LIBELLES_CLASSES, nombre, pourcent } from "@/lib/format";
import { INFO_BULLE, TEXTE, TEXTE_FORT } from "@/lib/theme";

interface Region {
  region: string;
  taux: number;
  provinces: ProvinceNationale[];
  eleve: number;
  alertes: number;
}

export default function VueRegions() {
  const [population, setPopulation] = usePopulation();
  const routeur = useRouter();
  const { donnees: n, erreur } = useApi<National>(`/api/national?population=${population}`);
  const { donnees: carte } = useApi<DonneesCarte>("/api/carte");
  const [k, setK] = useState(1);
  const [choisie, setChoisie] = useState<string | null>(null);
  const changerAnnee = useCallback((x: number) => setK(x), []);

  const regions = useMemo<Region[]>(() => {
    if (!n) return [];
    const groupes: Record<string, ProvinceNationale[]> = {};
    n.provinces.forEach((p) => (groupes[p.region] ??= []).push(p));
    return Object.entries(groupes)
      .map(([region, ps]) => {
        const valides = ps.filter((p) => p.serie[k].taux !== null);
        const poids = valides.reduce((a, p) => a + (p.poids || 1), 0);
        const taux = valides.reduce((a, p) => a + (p.serie[k].taux ?? 0) * (p.poids || 1), 0) / (poids || 1);
        return {
          region,
          taux,
          provinces: [...ps].sort((a, b) => (b.serie[k].taux ?? 0) - (a.serie[k].taux ?? 0)),
          eleve: ps.filter((p) => p.serie[k].classe === "élevé").length,
          alertes: ps.filter((p) => p.rupture === "élevé").length,
        };
      })
      .sort((a, b) => b.taux - a.taux);
  }, [n, k]);

  const region = regions.find((r) => r.region === choisie) ?? regions[0];
  const couleurs = useMemo(
    () => (n ? Object.fromEntries(regions.map((r) => [r.region, COULEURS_CLASSES[classeDe(r.taux, n.seuils)]])) : undefined),
    [regions, n],
  );
  const parNom = useMemo(() => Object.fromEntries(regions.map((r) => [r.region, r])), [regions]);

  const optionClassement = useMemo(() => {
    if (!n) return null;
    return {
      grid: { left: 4, right: 52, top: 2, bottom: 2, containLabel: true },
      tooltip: {
        ...INFO_BULLE,
        trigger: "item",
        formatter: (x: { dataIndex: number }) => {
          const r = regions[x.dataIndex];
          return `<b>${r.region}</b><br/>Taux pondéré : <b>${pourcent(r.taux)}</b><br/>${r.provinces.length} provinces · ${r.eleve} en risque élevé · ${r.alertes} alertes de rupture`;
        },
      },
      xAxis: { type: "value", show: false },
      yAxis: {
        type: "category",
        inverse: true,
        data: regions.map((r) => r.region),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: TEXTE_FORT, fontSize: 12 },
      },
      series: [
        {
          type: "bar",
          barWidth: 13,
          data: regions.map((r) => ({
            value: Number(r.taux.toFixed(2)),
            itemStyle: {
              color: COULEURS_CLASSES[classeDe(r.taux, n.seuils)],
              borderRadius: [0, 4, 4, 0],
              opacity: region && r.region !== region.region ? 0.55 : 1,
            },
          })),
          label: { show: true, position: "right", color: TEXTE, fontSize: 11.5, formatter: (x: { value: number }) => pourcent(x.value) },
        },
      ],
    };
  }, [regions, n, region]);

  if (erreur) return <Erreur message={erreur} />;
  if (!n || !region) return <Chargement />;
  const annee = n.annees[k];

  return (
    <>
      <header className="entete compacte">
        <h1>
          Vue régions <em>· 17 régions du découpage de 2025</em>
        </h1>
        <div className="commandes">
          <BasculePopulation valeur={population} changer={setPopulation} />
          <CurseurAnnees annees={n.annees} valeur={k} changer={changerAnnee} />
          <TiroirAlertes alertes={n.alertes} population={population} />
        </div>
      </header>

      <div className="grille g-regions">
        <section className="panneau">
          <div className="panneau-titre">
            <h2>
              Taux régional · {annee} <span className="etiquette-nature">{k === 0 ? "observé" : "prévision"}</span>
            </h2>
            <p>Moyenne des provinces pondérée par leurs effectifs du primaire. Cliquez une région.</p>
          </div>
          {carte && couleurs ? (
            <Carte
              donnees={carte}
              mode="regions"
              couleursRegions={couleurs}
              selection={region.region}
              surClic={setChoisie}
              infoRegion={(nom) => {
                const r = parNom[nom];
                if (!r) return null;
                return (
                  <>
                    <strong>{nom}</strong>
                    <div className="ligne">
                      {annee} <b>{pourcent(r.taux)}</b>
                    </div>
                    <div className="ligne">
                      Provinces en risque élevé <b>{r.eleve} / {r.provinces.length}</b>
                    </div>
                    <div className="ligne">
                      Alertes de rupture <b>{r.alertes}</b>
                    </div>
                  </>
                );
              }}
              enfants={
                <div className="legende">
                  {(["faible", "moyen", "élevé"] as Classe[]).map((c) => (
                    <div key={c} className="legende-ligne">
                      <span className="pastille" style={{ background: COULEURS_CLASSES[c] }} />
                      {LIBELLES_CLASSES[c]}
                    </div>
                  ))}
                </div>
              }
            />
          ) : (
            <div className="carte-conteneur" />
          )}
        </section>

        <section className="panneau">
          <div className="panneau-titre">
            <h2>
              Classement des régions <span className="etiquette-nature">{annee}</span>
            </h2>
          </div>
          {optionClassement ? (
            <Graphique option={optionClassement} hauteur={540} libelle={`Classement des régions, ${annee}`} surClic={(x) => setChoisie(regions[x.dataIndex].region)} />
          ) : null}
        </section>

        <section className="panneau">
          <div className="panneau-titre titre-avec-actions">
            <div>
            <h2>Région {region.region}</h2>
            <p>
              {pourcent(region.taux)} en {annee} · {region.provinces.length} provinces · {region.alertes} alerte{region.alertes > 1 ? "s" : ""} de rupture
            </p>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <a
                className="bouton secondaire petit"
                href={`/api/telechargement/previsions?population=${population}&region=${encodeURIComponent(region.region)}`}
                title="Prévisions 2025-2028 des provinces de la région (CSV pour Excel)"
              >
                <IconeTableur taille={16} /> Données
              </a>
              <a className="bouton secondaire petit" href={`/api/rapport/region/${encodeURIComponent(region.region)}?population=${population}`}>
                <IconeRapport taille={16} /> Rapport
              </a>
            </div>
          </div>
          <ul className="liste-provinces">
            {region.provinces.map((p) => {
              const s = p.serie[k];
              return (
                <li key={p.pcode}>
                  <button onClick={() => routeur.push(avecPopulation(`/province/${p.pcode}`, population))}>
                    <span>
                      <b>{p.province}</b>
                      <small>{s.bas !== null && s.haut !== null ? intervalle(s.bas, s.haut) : "observé"}</small>
                    </span>
                    <span className="droite">
                      <b>{pourcent(s.taux)}</b>
                      {s.classe ? <Badge classe={s.classe} /> : null}
                      {p.rupture === "élevé" ? <span className="marque-rupture" title={`Score de rupture ${nombre(p.score_rupture, 2)}`}>rupture</span> : null}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      </div>
    </>
  );
}
