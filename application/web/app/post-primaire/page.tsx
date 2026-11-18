"use client";

import Link from "next/link";
import { Chargement, Erreur } from "@/components/Etat";
import { useApi, type PostPrimaire } from "@/lib/api";
import { COULEURS_CLASSES, nombre, pourcent } from "@/lib/format";

// Classes propres au post-primaire, où les taux sont bien plus élevés qu'au primaire.
const SEUILS = { moyen: 15, eleve: 30 };
const couleur = (t: number) => (t >= SEUILS.eleve ? COULEURS_CLASSES["élevé"] : t >= SEUILS.moyen ? COULEURS_CLASSES.moyen : COULEURS_CLASSES.faible);

export default function VuePostPrimaire() {
  const { donnees: d, erreur } = useApi<PostPrimaire>("/api/post_primaire");
  if (erreur) return <Erreur message={erreur} />;
  if (!d) return <Chargement />;

  const fiables = d.provinces.filter((p) => p.fiable).sort((a, b) => b.taux - a.taux);
  const autres = d.provinces.filter((p) => !p.fiable);
  const premiere = d.medianes[0];
  const derniere = d.medianes[d.medianes.length - 1];
  const eleves = fiables.filter((p) => p.taux >= SEUILS.eleve).length;
  const hausse = fiables.filter((p) => p.serie[p.serie.length - 1].taux > p.serie[0].taux).length;
  const max = Math.max(...fiables.map((p) => p.taux), 1);

  return (
    <>
      <header className="entete compacte">
        <h1>
          Post-primaire <em>· abandon en 6e, 5e et 4e, valeurs observées</em>
        </h1>
      </header>

      <section className="tuiles tuiles-4" aria-label="Indicateurs clés du post-primaire">
        <div className="tuile" style={{ "--teinte": "#fcd116" } as React.CSSProperties}>
          <div className="tuile-valeur">{pourcent(derniere.mediane)}</div>
          <div className="tuile-libelle">
            Province médiane · <b>{derniere.annee}</b>
          </div>
          <div className="note" style={{ marginTop: 4 }}>
            contre {pourcent(premiere.mediane)} en {premiere.annee}
          </div>
        </div>
        <div className="tuile" style={{ "--teinte": COULEURS_CLASSES["élevé"] } as React.CSSProperties}>
          <div className="tuile-valeur">
            {eleves} <small>/ {fiables.length}</small>
          </div>
          <div className="tuile-libelle">Provinces à 30 % ou plus</div>
        </div>
        <div className="tuile" style={{ "--teinte": COULEURS_CLASSES.moyen } as React.CSSProperties}>
          <div className="tuile-valeur">
            {hausse} <small>/ {fiables.length}</small>
          </div>
          <div className="tuile-libelle">
            En hausse depuis {premiere.annee}
          </div>
        </div>
        <div className="tuile" style={{ "--teinte": "#8293ad" } as React.CSSProperties}>
          <div className="tuile-valeur">{d.non_interpretables}</div>
          <div className="tuile-libelle">Valeurs non interprétables (écoles fermées)</div>
        </div>
      </section>

      <div className="grille grille-deux">
        <section className="panneau">
          <div className="panneau-titre">
            <h2>Taux d&apos;abandon au post-primaire, {d.annee}</h2>
            <p>Moyenne des classes de 6e, 5e et 4e (DGESS, annuaires du post-primaire). Cliquez une province pour ouvrir sa fiche.</p>
          </div>
          <ol className="barres-pp">
            {fiables.map((p, i) => (
              <li key={p.pcode}>
                <Link href={`/province/${p.pcode}`} className="barre-pp" title={`${p.province} (${p.region})`}>
                  <span className="barre-pp-nom">
                    {i + 1}. {p.province}
                  </span>
                  <span className="barre-pp-piste">
                    <span style={{ width: `${(100 * p.taux) / max}%`, background: couleur(p.taux) }} />
                  </span>
                  <span className="barre-pp-valeur">{pourcent(p.taux)}</span>
                </Link>
              </li>
            ))}
          </ol>
        </section>

        <div className="colonne">
          <section className="panneau">
            <div className="panneau-titre">
              <h2>Une hausse nette depuis 2018-2019</h2>
              <p>Taux de la province médiane, années observées.</p>
            </div>
            <div className="evolution-pp">
              {d.medianes.map((m) => (
                <div key={m.annee} className="evolution-pp-col">
                  <span className="evolution-pp-valeur">{pourcent(m.mediane)}</span>
                  <span className="evolution-pp-barre" style={{ height: `${(140 * m.mediane) / derniere.mediane / 1.15}px` }} />
                  <span className="note">{m.annee}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="panneau">
            <div className="panneau-titre">
              <h2>Pourquoi pas de prévision ici</h2>
            </div>
            <p className="texte-pp">
              Le taux d&apos;abandon au post-primaire n&apos;est publié que pour {d.annees.length} années ({d.annees.join(", ")}).
              Prévoir 2025-2026 demanderait de projeter trois ans au-delà de la dernière observation, sans aucune année
              pour vérifier la fiabilité du modèle. Au primaire, neuf années et une année de test jamais vue le permettent.
              Cette vue montre donc les valeurs observées ; la prévision viendra dès que les annuaires suivants seront
              publiés, avec la même méthode que pour le primaire.
            </p>
            {autres.length ? (
              <p className="note" style={{ marginTop: 10 }}>
                Non interprétables en {d.annee} (presque aucune entrée en 6e, écoles fermées) :{" "}
                {autres.map((p) => `${p.province} (${nombre(p.taux, 0)} %)`).join(", ")}.
              </p>
            ) : null}
          </section>
        </div>
      </div>
    </>
  );
}
