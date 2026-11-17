"use client";

import { useEffect, useState } from "react";
import { ArrowRight, RotateCcw } from "lucide-react";
import Badge from "@/components/Badge";
import { Chargement, Erreur } from "@/components/Etat";
import { envoyer, useApi, type Leviers, type Meta, type Simulation } from "@/lib/api";
import { COULEURS_CLASSES, nombre, pourcent } from "@/lib/format";

function Echelle({ prevu, simule, seuils }: { prevu: number; simule: number; seuils: { moyen: number; eleve: number } }) {
  const max = Math.max(30, Math.ceil(Math.max(prevu, simule) / 5) * 5 + 5);
  const x = (v: number) => `${(100 * Math.min(Math.max(v, 0), max)) / max}%`;
  return (
    <div className="echelle" role="img" aria-label={`Prévision ${pourcent(prevu)}, scénario ${pourcent(simule)}`}>
      <div className="echelle-bande" style={{ left: 0, width: x(seuils.moyen), background: COULEURS_CLASSES.faible }} />
      <div className="echelle-bande" style={{ left: x(seuils.moyen), width: `calc(${x(seuils.eleve)} - ${x(seuils.moyen)})`, background: COULEURS_CLASSES.moyen }} />
      <div className="echelle-bande" style={{ left: x(seuils.eleve), right: 0, background: COULEURS_CLASSES["élevé"] }} />
      <div className="echelle-repere" style={{ left: x(prevu), color: "#cbd5e1" }}>
        <span>actuel</span>
        <i style={{ background: "#cbd5e1" }} />
      </div>
      <div className="echelle-repere" style={{ left: x(simule), color: "#2fbf7f", top: 0 }}>
        <span style={{ transform: "translateY(62px)" }}>scénario</span>
        <i style={{ background: "#2fbf7f" }} />
      </div>
      {[0, seuils.moyen, seuils.eleve, max].map((v) => (
        <span key={v} className="echelle-graduation" style={{ left: x(v), top: 40 }}>
          {nombre(v, v % 1 ? 1 : 0)} %
        </span>
      ))}
    </div>
  );
}

export default function Simulateur() {
  const [pcode, setPcode] = useState("BF5401");
  const { donnees: meta } = useApi<Meta>("/api/meta");
  const { donnees: l, erreur } = useApi<Leviers>(`/api/simulateur/${pcode}`);
  const [valeurs, setValeurs] = useState<Record<string, number>>({});
  const [resultat, setResultat] = useState<Simulation | null>(null);

  useEffect(() => {
    if (l) setValeurs(Object.fromEntries(l.leviers.map((v) => [v.variable, v.valeur])));
  }, [l]);

  useEffect(() => {
    if (!l || !Object.keys(valeurs).length) return;
    const minuterie = setTimeout(() => {
      envoyer<Simulation>("/api/simulateur", { pcode, valeurs }).then(setResultat).catch(() => setResultat(null));
    }, 180);
    return () => clearTimeout(minuterie);
  }, [valeurs, l, pcode]);

  if (erreur) return <Erreur message={erreur} />;
  if (!l) return <Chargement />;

  const reinitialiser = () => setValeurs(Object.fromEntries(l.leviers.map((v) => [v.variable, v.valeur])));
  const mediane = () => setValeurs(Object.fromEntries(l.leviers.map((v) => [v.variable, v.mediane_provinces])));
  const r = resultat;

  return (
    <>
      <header className="entete compacte">
        <h1>
          Simulateur de leviers <em>· et si les conditions changeaient ?</em>
        </h1>
        <div className="commandes">
          <label className="champ">
            <select aria-label="Province" className="select" value={pcode} onChange={(e) => setPcode(e.target.value)}>
              {meta?.regions.map((reg) => (
                <optgroup key={reg} label={reg}>
                  {meta.provinces
                    .filter((p) => p.region === reg)
                    .map((p) => (
                      <option key={p.pcode} value={p.pcode}>
                        {p.province}
                      </option>
                    ))}
                </optgroup>
              ))}
            </select>
          </label>
        </div>
      </header>

      <div className="grille grille-deux">
        <section className="panneau">
          <div className="panneau-titre titre-avec-actions">
            <div>
              <h2>{l.province} : leviers</h2>
              <p>Valeurs moyennes 2016-2025 · repère : province médiane du pays.</p>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="bouton secondaire" onClick={mediane}>
                Aligner sur la médiane
              </button>
              <button className="bouton secondaire" onClick={reinitialiser} aria-label="Revenir aux valeurs de la province">
                <RotateCcw size={16} />
              </button>
            </div>
          </div>
          {l.leviers.map((v) => {
            const valeur = valeurs[v.variable] ?? v.valeur;
            const effet = (valeur - v.valeur) * v.effet_par_unite;
            const pas = (v.maximum - v.minimum) / 200;
            return (
              <div key={v.variable} className="levier">
                <div className="levier-entete">
                  <div>
                    <b>{v.libelle}</b>
                    <div className="note" style={{ marginTop: 2 }}>
                      {v.effet_par_unite >= 0 ? "+" : "−"}
                      {nombre(Math.abs(v.effet_par_unite), 2)} point de taux par {v.unite === "%" ? "point de pourcentage" : "unité"}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <b style={{ fontSize: 18 }}>
                      {nombre(valeur, 1)}
                      {v.unite ? ` ${v.unite}` : ""}
                    </b>
                    <div className="note" style={{ marginTop: 2, color: effet > 0.05 ? "#ff8fa3" : effet < -0.05 ? "#6ee7b7" : undefined }}>
                      {Math.abs(effet) < 0.05 ? "inchangé" : `${effet > 0 ? "+" : "−"}${nombre(Math.abs(effet), 1)} point`}
                    </div>
                  </div>
                </div>
                <input
                  type="range"
                  min={v.minimum}
                  max={v.maximum}
                  step={pas}
                  value={valeur}
                  onChange={(e) => setValeurs({ ...valeurs, [v.variable]: Number(e.target.value) })}
                  aria-label={v.libelle}
                />
                <div className="levier-reperes">
                  <span>{nombre(v.minimum, 1)}</span>
                  <span>
                    actuelle {nombre(v.valeur, 1)} · médiane {nombre(v.mediane_provinces, 1)}
                  </span>
                  <span>{nombre(v.maximum, 1)}</span>
                </div>
              </div>
            );
          })}
        </section>

        <div className="colonne">
          <section className="panneau">
            <div className="panneau-titre">
              <h2>{l.province} : taux attendu en 2025-2026</h2>
            </div>
            <div className="resultat">
              <div>
                <div className="note">Prévision actuelle</div>
                <div className="grand-nombre">{pourcent(l.taux)}</div>
                <Badge classe={l.classe} />
              </div>
              <ArrowRight size={28} color="#8293ad" />
              <div>
                <div className="note">Avec ces caractéristiques</div>
                <div className="grand-nombre" style={{ color: r ? COULEURS_CLASSES[r.classe_simulee] : undefined }}>
                  {r ? pourcent(r.taux_simule) : "…"}
                </div>
                {r ? <Badge classe={r.classe_simulee} /> : null}
              </div>
            </div>
            {r ? (
              <p style={{ textAlign: "center", marginTop: 16, fontSize: 15 }}>
                Écart :{" "}
                <b style={{ color: r.ecart > 0.05 ? "#ff8fa3" : r.ecart < -0.05 ? "#6ee7b7" : "var(--texte)" }}>
                  {r.ecart > 0 ? "+" : r.ecart < 0 ? "−" : ""}
                  {nombre(Math.abs(r.ecart), 1)} point{Math.abs(r.ecart) >= 2 ? "s" : ""}
                </b>
              </p>
            ) : null}
          </section>

          <section className="panneau">
            <div className="panneau-titre">
              <h2>{l.province} : position sur l&apos;échelle de risque</h2>
              <p>Associations mesurées entre provinces (R² {nombre(l.r2, 2)} sur provinces non vues), pas des effets garantis.</p>
            </div>
            <Echelle prevu={l.taux} simule={r?.taux_simule ?? l.taux} seuils={l.seuils} />
          </section>
        </div>
      </div>
    </>
  );
}
