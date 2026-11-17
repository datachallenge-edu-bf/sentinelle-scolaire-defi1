"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Badge from "@/components/Badge";
import { Chargement, Erreur } from "@/components/Etat";
import { envoyer, useApi, type Classe } from "@/lib/api";
import { COULEURS_CLASSES, intervalle, nombre, pourcent } from "@/lib/format";

interface Etat {
  derniere_annee: string;
  annee_attendue: string;
  annees_saisies: string[];
  provinces: { pcode: string; province: string; region: string; repere_taux: number; repere_eleves: number }[];
}

interface Resultat {
  pcode: string;
  province: string;
  region: string;
  saisie: boolean;
  avant: number;
  classe_avant: Classe;
  taux_saisi?: number;
  evolution_effectifs?: number;
  rupture_annee?: boolean;
  previsions: { annee: string; taux: number; bas: number; haut: number; classe: Classe }[];
  score_rupture: number;
  risque_rupture: Classe;
  filles?: number;
  garcons?: number;
}

interface Apercu {
  annee: string;
  annees_prevues: string[];
  messages: { niveau: "erreur" | "attention"; texte: string }[];
  provinces_saisies: number;
  resultats: Resultat[];
  resume: { changements_de_classe: number; ruptures_detectees: number; alertes_elevees: number; eleve: number; moyen: number; faible: number };
}

type Valeurs = Record<string, { taux: string; eleves: string; filles: string; garcons: string }>;
const VIDE = { taux: "", eleves: "", filles: "", garcons: "" };
const nombreSaisi = (x: string) => (x.trim() === "" ? null : Number(x.replace(",", ".").replace(/\s/g, "")));

export default function MiseAJour() {
  const [version, setVersion] = useState(0);
  const { donnees: etat, erreur } = useApi<Etat>(`/api/mise_a_jour/etat?v=${version}`);
  const [valeurs, setValeurs] = useState<Valeurs>({});
  const [apercu, setApercu] = useState<Apercu | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [calcul, setCalcul] = useState(false);
  const fichier = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setValeurs({});
    setApercu(null);
  }, [etat?.annee_attendue]);

  const lignes = useMemo(
    () =>
      Object.entries(valeurs)
        .map(([pcode, v]) => ({
          province_pcode: pcode,
          taux_abandon_primaire: nombreSaisi(v.taux),
          eleves_primaire: nombreSaisi(v.eleves),
          taux_abandon_filles: nombreSaisi(v.filles),
          taux_abandon_garcons: nombreSaisi(v.garcons),
        }))
        .filter((l) => l.taux_abandon_primaire !== null || l.eleves_primaire !== null),
    [valeurs],
  );

  const calculer = async () => {
    setCalcul(true);
    setMessage(null);
    try {
      setApercu(await envoyer<Apercu>("/api/mise_a_jour/apercu", { lignes }));
    } catch (e) {
      setMessage(`Calcul impossible : ${String(e)}`);
    } finally {
      setCalcul(false);
    }
  };

  const importer = async (f: File) => {
    const texte = await f.text();
    try {
      const r = await envoyer<{ lignes: Record<string, string | number | null>[] }>("/api/mise_a_jour/lire", { csv: texte });
      const suite: Valeurs = {};
      for (const l of r.lignes) {
        const pcode = String(l.province_pcode ?? "").trim();
        if (!pcode) continue;
        const t = (x: unknown) => (x === null || x === undefined ? "" : String(x).replace(".", ","));
        suite[pcode] = { taux: t(l.taux_abandon_primaire), eleves: t(l.eleves_primaire), filles: t(l.taux_abandon_filles), garcons: t(l.taux_abandon_garcons) };
      }
      setValeurs(suite);
      setApercu(null);
      setMessage(`${Object.values(suite).filter((v) => v.taux && v.eleves).length} provinces complètes importées depuis ${f.name}.`);
    } catch (e) {
      setMessage(`Import impossible : ${String(e)}`);
    }
  };

  const enregistrer = async () => {
    const r = await envoyer<{ enregistre: boolean; annee?: string; messages: { texte: string }[] }>("/api/mise_a_jour/enregistrer", { lignes });
    if (r.enregistre) {
      setMessage(`Données ${r.annee} enregistrées dans data/05_mises_a_jour/. Les prévisions sont téléchargeables.`);
      setVersion((v) => v + 1);
      window.open(`/api/mise_a_jour/previsions/${r.annee}.csv`, "_blank");
    } else {
      setMessage(r.messages.map((m) => m.texte).join(" "));
    }
  };

  const retirer = async (annee: string) => {
    if (!window.confirm(`Retirer les données saisies pour ${annee} ? Les prévisions reviendront à l'année précédente.`)) return;
    await fetch(`/api/mise_a_jour/${annee}`, { method: "DELETE" });
    setMessage(`Données ${annee} retirées.`);
    setVersion((v) => v + 1);
  };

  if (erreur) return <Erreur message={erreur} />;
  if (!etat) return <Chargement />;
  const derniereSaisie = etat.annees_saisies[etat.annees_saisies.length - 1];

  return (
    <>
      <header className="entete compacte">
        <h1>
          Mise à jour des données <em>· nouvelle année {etat.annee_attendue}</em>
        </h1>
        <div className="commandes">
          <a className="bouton secondaire" href="/api/mise_a_jour/modele.csv">
            Modèle CSV à remplir
          </a>
          <button className="bouton secondaire" onClick={() => fichier.current?.click()}>
            Importer un fichier
          </button>
          <input ref={fichier} type="file" accept=".csv,text/csv" hidden onChange={(e) => e.target.files?.[0] && importer(e.target.files[0])} />
          <button className="bouton" onClick={calculer} disabled={calcul}>
            {calcul ? "Calcul…" : "Calculer les prévisions"}
          </button>
        </div>
      </header>

      <div className="bandeau-etat">
        Dernières données : <b>{etat.derniere_annee}</b>
        {etat.annees_saisies.length ? <> (saisies par l&apos;utilisateur : {etat.annees_saisies.join(", ")})</> : <> (officielles)</>} · prévisions calculées
        pour les trois années suivant {etat.annee_attendue}, avec les modèles et marges sauvegardés.
        {derniereSaisie ? (
          <>
            {" "}
            <a href={`/api/mise_a_jour/previsions/${derniereSaisie}.csv`}>Prévisions {derniereSaisie} (CSV)</a> ·{" "}
            <button className="lien" onClick={() => retirer(derniereSaisie)}>
              retirer {derniereSaisie}
            </button>
          </>
        ) : null}
        {message ? <div className="message-etat">{message}</div> : null}
      </div>

      <div className="grille g-maj">
        <section className="panneau">
          <div className="panneau-titre">
            <h2>Saisie {etat.annee_attendue}</h2>
            <p>Taux d&apos;abandon en %, effectif du primaire en élèves. Filles et garçons : facultatifs.</p>
          </div>
          <div className="table-saisie">
            <table className="tableau">
              <thead>
                <tr>
                  <th>Province</th>
                  <th className="nombre">Taux {etat.derniere_annee}</th>
                  <th>Taux {etat.annee_attendue}</th>
                  <th>Effectif</th>
                  <th>Filles</th>
                  <th>Garçons</th>
                </tr>
              </thead>
              <tbody>
                {etat.provinces.map((p) => {
                  const v = valeurs[p.pcode] ?? VIDE;
                  const changer = (cle: keyof typeof VIDE, x: string) => setValeurs({ ...valeurs, [p.pcode]: { ...v, [cle]: x } });
                  return (
                    <tr key={p.pcode}>
                      <td style={{ color: "var(--texte)" }}>
                        {p.province}
                        <small className="sous">{p.region}</small>
                      </td>
                      <td className="nombre">{nombre(p.repere_taux)}</td>
                      <td>
                        <input className="cellule" inputMode="decimal" value={v.taux} onChange={(e) => changer("taux", e.target.value)} aria-label={`Taux ${p.province}`} />
                      </td>
                      <td>
                        <input className="cellule large" inputMode="numeric" value={v.eleves} placeholder={String(p.repere_eleves)} onChange={(e) => changer("eleves", e.target.value)} aria-label={`Effectif ${p.province}`} />
                      </td>
                      <td>
                        <input className="cellule" inputMode="decimal" value={v.filles} onChange={(e) => changer("filles", e.target.value)} aria-label={`Taux des filles ${p.province}`} />
                      </td>
                      <td>
                        <input className="cellule" inputMode="decimal" value={v.garcons} onChange={(e) => changer("garcons", e.target.value)} aria-label={`Taux des garçons ${p.province}`} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panneau">
          <div className="panneau-titre titre-avec-actions">
            <div>
              <h2>Aperçu des nouvelles prévisions</h2>
              <p>{apercu ? `${apercu.provinces_saisies} provinces saisies · prévisions ${apercu.annees_prevues.join(", ")}` : "Saisissez ou importez des données, puis calculez."}</p>
            </div>
            {apercu && apercu.provinces_saisies > 0 && !apercu.messages.some((m) => m.niveau === "erreur") ? (
              <button className="bouton" onClick={enregistrer}>
                Enregistrer {apercu.annee}
              </button>
            ) : null}
          </div>
          {apercu ? (
            <>
              {apercu.messages.map((m, i) => (
                <div key={i} className={`controle ${m.niveau}`}>
                  {m.niveau === "erreur" ? "Erreur" : "Attention"} : {m.texte}
                </div>
              ))}
              <div className="resume-maj">
                {(
                  [
                    [apercu.resume.eleve, "risque élevé", COULEURS_CLASSES["élevé"]],
                    [apercu.resume.changements_de_classe, "changements de classe", "#38bdf8"],
                    [apercu.resume.ruptures_detectees, "ruptures détectées", "#8b5cf6"],
                    [apercu.resume.alertes_elevees, "alertes de rupture", "#8b5cf6"],
                  ] as [number, string, string][]
                ).map(([v, l, c]) => (
                  <div key={l} style={{ borderTopColor: c }}>
                    <b>{v}</b>
                    <span>{l}</span>
                  </div>
                ))}
              </div>
              <div className="table-saisie" style={{ maxHeight: 400 }}>
                <table className="tableau">
                  <thead>
                    <tr>
                      <th>Province</th>
                      <th className="nombre">Avant</th>
                      <th className="nombre">{apercu.annees_prevues[0]}</th>
                      <th>Intervalle à 80 %</th>
                      <th>Classe</th>
                      <th className="nombre">Rupture</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apercu.resultats.map((r) => {
                      const p = r.previsions[0];
                      const change = p.classe !== r.classe_avant;
                      return (
                        <tr key={r.pcode} className={change ? "choisie" : ""}>
                          <td style={{ color: "var(--texte)" }}>
                            {r.province}
                            {r.saisie ? null : <small className="sous">non saisie</small>}
                            {r.rupture_annee ? <span className="marque-rupture" style={{ marginLeft: 6 }}>rupture</span> : null}
                          </td>
                          <td className="nombre">{pourcent(r.avant)}</td>
                          <td className="nombre" style={{ color: "var(--texte)", fontWeight: 600 }}>
                            {pourcent(p.taux)}
                          </td>
                          <td>{intervalle(p.bas, p.haut)}</td>
                          <td>
                            {change ? <Badge classe={r.classe_avant} /> : null}
                            {change ? " → " : null}
                            <Badge classe={p.classe} />
                          </td>
                          <td className="nombre">{nombre(r.score_rupture, 2)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <ol className="etapes">
              <li>Téléchargez le modèle CSV (47 provinces, valeurs {etat.derniere_annee} pour repère), ou saisissez directement à gauche.</li>
              <li>Renseignez le taux d&apos;abandon et l&apos;effectif de l&apos;annuaire {etat.annee_attendue}.</li>
              <li>Calculez : contrôles, nouvelles prévisions et changements de classe s&apos;affichent ici.</li>
              <li>Enregistrez : les données sont rangées à part, sans toucher aux données officielles.</li>
            </ol>
          )}
        </section>
      </div>
    </>
  );
}
