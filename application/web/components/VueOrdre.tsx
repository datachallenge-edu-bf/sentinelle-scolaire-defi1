"use client";

import { useMemo, useState } from "react";
import BasculePopulation from "./BasculePopulation";
import ComparaisonOrdres from "./ComparaisonOrdres";
import { Carte } from "./dynamique";
import { Chargement, Erreur } from "./Etat";
import { usePopulation } from "./usePopulation";
import { useApi, type Carte as DonneesCarte, type VueOrdre as Donnees } from "@/lib/api";
import { COULEURS_CLASSES, LIBELLES_CLASSES, pourcent } from "@/lib/format";

const TITRES = {
  post_primaire: { titre: "Post-primaire", sous: "abandon en 6e, 5e et 4e", entree: "Entrée en 6e" },
  secondaire: { titre: "Secondaire", sous: "abandon en 2nde et 1re", entree: "Entrée en 2nde" },
};

/** Vue nationale d'un ordre d'enseignement après le primaire : valeurs observées, sans prévision. */
export default function VueOrdre({ ordre }: { ordre: "post_primaire" | "secondaire" }) {
  const [population, setPopulation] = usePopulation();
  const { donnees: d, erreur } = useApi<Donnees>(`/api/ordre/${ordre}?population=${population}`);
  const { donnees: carte } = useApi<DonneesCarte>("/api/carte");
  const [choix, setChoix] = useState<number | null>(null);
  const t = TITRES[ordre];
  const k = choix ?? (d ? d.annees.length - 1 : 0);

  const carteAnnee = useMemo<DonneesCarte | null>(() => {
    if (!carte || !d) return null;
    const parCode = Object.fromEntries(d.provinces.map((p) => [p.pcode, p]));
    return {
      ...carte,
      provinces: {
        ...carte.provinces,
        features: carte.provinces.features.map((f) => {
          const s = parCode[String(f.properties?.province_pcode)]?.serie[k];
          return { ...f, properties: { ...f.properties, classe: s?.classe ?? "", taux: s?.taux ?? null, rupture: "", scindee: false } };
        }),
      },
    };
  }, [carte, d, k]);
  const etiquettes = useMemo(
    () => Object.fromEntries((d?.provinces ?? []).map((p) => [p.pcode, `${p.province}\n${p.serie[k]?.taux != null ? pourcent(p.serie[k].taux) : "–"}`])),
    [d, k],
  );

  if (erreur) return <Erreur message={erreur} />;
  if (!d) return <Chargement />;

  const m = d.medianes[k];
  const valides = d.provinces.filter((p) => p.serie[k].taux != null).sort((a, b) => b.serie[k].taux! - a.serie[k].taux!);
  const eleves = valides.filter((p) => p.serie[k].classe === "élevé").length;
  const hausse = valides.filter((p) => p.serie[0].taux != null && p.serie[k].taux! > p.serie[0].taux!).length;
  const max = Math.max(...valides.map((p) => p.serie[k].taux!), 1);
  const tete = valides[0];

  return (
    <>
      <header className="entete">
        <h1>
          {t.titre} <em>· {t.sous}</em>
        </h1>
        <div className="commandes">
          <BasculePopulation valeur={population} changer={setPopulation} />
          <div className="bascule" role="radiogroup" aria-label="Année observée">
            {d.annees.map((a, i) => (
              <button key={a} role="radio" aria-checked={i === k} className={i === k ? "actif" : ""} onClick={() => setChoix(i)}>
                {a}
              </button>
            ))}
          </div>
        </div>
      </header>

      <ComparaisonOrdres population={population} />

      <section className="tuiles tuiles-5" aria-label="Indicateurs clés">
        <div className="tuile" style={{ "--teinte": "#fcd116" } as React.CSSProperties}>
          <div className="tuile-valeur">{pourcent(m.mediane)}</div>
          <div className="tuile-libelle">
            Province médiane · <b>{m.annee}</b>
          </div>
        </div>
        <div className="tuile" style={{ "--teinte": COULEURS_CLASSES["élevé"] } as React.CSSProperties}>
          <div className="tuile-valeur">
            {eleves} <small>/ {valides.length}</small>
          </div>
          <div className="tuile-libelle">30 % ou plus</div>
        </div>
        <div className="tuile" style={{ "--teinte": COULEURS_CLASSES.moyen } as React.CSSProperties}>
          <div className="tuile-valeur">
            {hausse} <small>/ {valides.length}</small>
          </div>
          <div className="tuile-libelle">En hausse depuis {d.annees[0]}</div>
        </div>
        {tete ? (
          <div className="tuile" style={{ "--teinte": COULEURS_CLASSES["élevé"] } as React.CSSProperties}>
            <div className="tuile-valeur">{pourcent(tete.serie[k].taux)}</div>
            <div className="tuile-libelle">
              Plus élevé : <b>{tete.province}</b>
            </div>
          </div>
        ) : null}
        <div className="tuile" style={{ "--teinte": "#8293ad" } as React.CSSProperties} title="0 % ou plus de 90 % : presque aucun élève, écoles fermées">
          <div className="tuile-valeur">{m.non_interpretables}</div>
          <div className="tuile-libelle">Écoles fermées (non interprétable)</div>
        </div>
      </section>

      <div className="grille g-carte">
        <section className="panneau panneau-carte">
          <div className="panneau-titre">
            <h2>
              Burkina Faso · {m.annee} <span className="etiquette-nature">observé</span>
            </h2>
          </div>
          {carteAnnee ? (
            <Carte
              donnees={carteAnnee}
              couches={{ risque: true, rupture: false, limites: true, scindees: false }}
              etiquettesProvinces={etiquettes}
              infoProvince={(p) => (
                <>
                  <strong>{String(p.province_nom)}</strong> <span>· {String(p.region_nom)}</span>
                  <div className="ligne">
                    {m.annee} <b>{p.taux != null ? pourcent(p.taux as number) : "non interprétable"}</b>
                  </div>
                </>
              )}
              enfants={
                <div className="legende">
                  {(["faible", "moyen", "élevé"] as const).map((c) => (
                    <div key={c} className="legende-ligne">
                      <span className="pastille" style={{ background: COULEURS_CLASSES[c] }} />
                      {LIBELLES_CLASSES[c]} {c === "faible" ? "< 15 %" : c === "moyen" ? "15-30 %" : "≥ 30 %"}
                    </div>
                  ))}
                </div>
              }
            />
          ) : null}
        </section>

        <section className="panneau">
          <div className="panneau-titre">
            <h2>Classement · {m.annee}</h2>
          </div>
          <ol className="barres-pp">
            {valides.map((p, i) => (
              <li key={p.pcode} className="barre-pp" title={`${p.province} (${p.region}) · ${t.entree} ${pourcent(p.serie[k].entree)}`}>
                <span className="barre-pp-nom">
                  {i + 1}. {p.province}
                </span>
                <span className="barre-pp-piste">
                  <span style={{ width: `${(100 * p.serie[k].taux!) / max}%`, background: COULEURS_CLASSES[p.serie[k].classe ?? "faible"] }} />
                </span>
                <span className="barre-pp-valeur">{pourcent(p.serie[k].taux)}</span>
              </li>
            ))}
          </ol>
          <p className="note" style={{ marginTop: 10 }}>
            Taux publiés (DGESS) · un 0 publié compte comme non renseigné · pas de prévision : 4 années observées.
          </p>
        </section>
      </div>
    </>
  );
}
