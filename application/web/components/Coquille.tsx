"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { IconeGuide, IconeMiseAJour, IconeNationale, IconeProvince, IconeRegions, IconeSimulateur, Logo } from "./Icones";
import { useApi, type Meta } from "@/lib/api";
import { avecPopulation } from "@/lib/format";
import Assistant from "./Assistant";
import { usePopulation } from "./usePopulation";

const PROVINCE_PAR_DEFAUT = "BF5401";

export default function Coquille({ children }: { children: React.ReactNode }) {
  const chemin = usePathname();
  const routeur = useRouter();
  const [population] = usePopulation();
  const { donnees: meta } = useApi<Meta>("/api/meta");

  const provinceCourante = chemin.startsWith("/province/") ? chemin.split("/")[2] : PROVINCE_PAR_DEFAUT;
  const liens = [
    { href: "/", libelle: "Vue nationale", icone: <IconeNationale />, actif: chemin === "/" },
    {
      href: `/province/${provinceCourante}`,
      libelle: "Fiche province",
      icone: <IconeProvince />,
      actif: chemin.startsWith("/province"),
    },
    { href: "/regions", libelle: "Vue régions", icone: <IconeRegions />, actif: chemin.startsWith("/regions") },
    {
      href: "/post-primaire",
      libelle: "Post-primaire",
      icone: <IconeNationale />,
      actif: chemin.startsWith("/post-primaire"),
    },
    {
      href: "/simulateur",
      libelle: "Simulateur de leviers",
      icone: <IconeSimulateur />,
      actif: chemin.startsWith("/simulateur"),
    },
    {
      href: "/mise-a-jour",
      libelle: "Mise à jour des données",
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
      <aside className="barre-laterale">
        <div className="marque">
          <Logo />
          <div>
            <div className="marque-nom">
              Sentinelle <span>Scolaire</span>
            </div>
            <div className="marque-pays">
              <svg className="marque-etoile" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 2.5l2.6 6.9 7.4.3-5.8 4.6 2 7.1L12 17.3l-6.2 4.1 2-7.1L2 9.7l7.4-.3z" />
              </svg>
              Burkina Faso
            </div>
            <div className="marque-devise">Anticiper, comprendre et prévenir le décrochage au primaire</div>
          </div>
        </div>

        <nav className="navigation" aria-label="Navigation principale">
          {liens.map((l) => (
            <Link key={l.libelle} href={avecPopulation(l.href, population)} className={`lien-nav${l.actif ? " actif" : ""}`}>
              {l.icone}
              {l.libelle}
            </Link>
          ))}
        </nav>

        <a className="lien-nav lien-guide" href="/guide_sentinelle.pdf" download>
          <IconeGuide />
          Guide d&apos;utilisation (PDF)
        </a>

        <div>
          <div className="titre-section-laterale">Aller à une province</div>
          <select
            className="select"
            style={{ width: "100%", minWidth: 0 }}
            value={chemin.startsWith("/province/") ? provinceCourante : ""}
            onChange={(e) => e.target.value && routeur.push(avecPopulation(`/province/${e.target.value}`, population))}
            aria-label="Choisir une province"
          >
            <option value="">Choisir une province…</option>
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
        </div>

      </aside>
      <main className="contenu">{children}</main>
      <Assistant population={population} />
    </div>
  );
}
