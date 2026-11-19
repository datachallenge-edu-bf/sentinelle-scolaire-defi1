"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  IconeGuide,
  IconeMiseAJour,
  IconeNationale,
  IconeProvince,
  IconeRegions,
  IconeSimulateur,
  Logo,
} from "./Icones";
import { useApi, type Meta } from "@/lib/api";
import { avecPopulation } from "@/lib/format";
import Assistant from "./Assistant";
import { usePopulation } from "./usePopulation";

const PROVINCE_PAR_DEFAUT = "BF5401";

// Ordres d'enseignement : le primaire a tous les écrans ; post-primaire et secondaire, les valeurs observées.
const ORDRES = [
  { href: "/", libelle: "Primaire", cle: "primaire" },
  { href: "/post-primaire", libelle: "Post-primaire", cle: "post-primaire" },
  { href: "/secondaire", libelle: "Secondaire", cle: "secondaire" },
];

export default function Coquille({ children }: { children: React.ReactNode }) {
  const chemin = usePathname();
  const routeur = useRouter();
  const [population] = usePopulation();
  const { donnees: meta } = useApi<Meta>("/api/meta");

  const ordre = chemin.startsWith("/post-primaire")
    ? "post-primaire"
    : chemin.startsWith("/secondaire")
      ? "secondaire"
      : "primaire";
  const provinceCourante = chemin.startsWith("/province/")
    ? chemin.split("/")[2]
    : PROVINCE_PAR_DEFAUT;
  const liens = [
    {
      href: "/",
      libelle: "Vue nationale",
      icone: <IconeNationale />,
      actif: chemin === "/",
    },
    {
      href: `/province/${provinceCourante}`,
      libelle: "Fiche province",
      icone: <IconeProvince />,
      actif: chemin.startsWith("/province"),
    },
    {
      href: "/regions",
      libelle: "Vue régions",
      icone: <IconeRegions />,
      actif: chemin.startsWith("/regions"),
    },
    {
      href: "/simulateur",
      libelle: "Simulateur",
      icone: <IconeSimulateur />,
      actif: chemin.startsWith("/simulateur"),
    },
    {
      href: "/mise-a-jour",
      libelle: "Mise à jour",
      icone: <IconeMiseAJour />,
      actif: chemin.startsWith("/mise-a-jour"),
    },
  ];

  return (
    <div className="coquille">
      {/* Cadre aux couleurs du drapeau du Burkina Faso : rouge en haut, vert en bas, les deux sur les côtés. */}
      <div className="drapeau-cadre" aria-hidden="true">
        <span className="drapeau-haut" />
        <span className="drapeau-bas" />
        <span className="drapeau-gauche" />
        <span className="drapeau-droite" />
      </div>

      <header className="barre-haute">
        <div className="barre-ligne">
          <div className="marque">
            <Logo taille={34} />
            <div>
              <div className="marque-nom">
                Sentinelle <span>Scolaire</span>
              </div>
              <div className="marque-pays">
                <svg
                  className="marque-etoile"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path d="M12 2.5l2.6 6.9 7.4.3-5.8 4.6 2 7.1L12 17.3l-6.2 4.1 2-7.1L2 9.7l7.4-.3z" />
                </svg>
                Burkina Faso
              </div>
            </div>
          </div>

          <nav className="ordres" aria-label="Ordre d'enseignement">
            {ORDRES.map((o) => (
              <Link
                key={o.cle}
                href={avecPopulation(o.href, population)}
                className={`ordre${ordre === o.cle ? " actif" : ""}`}
              >
                {o.libelle}
              </Link>
            ))}
          </nav>
        </div>

        <div className="barre-ligne barre-ecrans">
          {ordre === "primaire" ? (
            <nav className="onglets" aria-label="Écrans du primaire">
              {liens.map((l) => (
                <Link
                  key={l.libelle}
                  href={avecPopulation(l.href, population)}
                  className={`onglet${l.actif ? " actif" : ""}`}
                >
                  {l.icone}
                  {l.libelle}
                </Link>
              ))}
            </nav>
          ) : (
            <nav className="onglets" aria-label="Écran">
              <span className="onglet actif">
                <IconeNationale />
                Vue nationale
              </span>
            </nav>
          )}

          <div className="barre-outils">
            {ordre === "primaire" ? (
              <select
                className="select"
                value={chemin.startsWith("/province/") ? provinceCourante : ""}
                onChange={(e) =>
                  e.target.value &&
                  routeur.push(
                    avecPopulation(`/province/${e.target.value}`, population),
                  )
                }
                aria-label="Aller à une province"
              >
                <option value="">Province…</option>
                {meta?.regions.map((r) => (
                  <optgroup key={r} label={r}>
                    {meta.provinces
                      .filter((p) => p.region === r)
                      .map((p) => (
                        <option key={p.pcode} value={p.pcode}>
                          {p.province}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>
            ) : null}
            <a
              className="onglet"
              href="/guide_sentinelle.pdf"
              download
              title="Guide d'utilisation (PDF)"
            >
              <IconeGuide />
              Guide
            </a>
          </div>
        </div>
      </header>
      <main className="contenu">{children}</main>
      <Assistant population={population} />
    </div>
  );
}
