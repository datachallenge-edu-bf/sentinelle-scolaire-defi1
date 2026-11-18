/** Pictogrammes propres à Sentinelle Scolaire : trait de 1,7 et un élément plein qui porte l'accent. */

type P = { taille?: number };

function Cadre({ taille = 20, children }: P & { children: React.ReactNode }) {
  return (
    <svg width={taille} height={taille} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

/** Logo : un œil de veille dont la pupille est une province. */
export function Logo({ taille = 38 }: P) {
  return (
    <svg width={taille} height={taille} viewBox="0 0 40 40" aria-hidden="true">
      <rect width="40" height="40" rx="11" fill="#103b2b" />
      <path d="M6 20c4.2-6.2 8.9-9.3 14-9.3S29.8 13.8 34 20c-4.2 6.2-8.9 9.3-14 9.3S10.2 26.2 6 20Z" fill="none" stroke="#2fbf7f" strokeWidth="2.2" />
      <path d="M16.2 17.4l3.1-2.6 4.3 1.1.9 3.6-2.2 3.4-4.1.4-2.4-2.6z" fill="#2fbf7f" />
      <circle cx="20.6" cy="19.1" r="1.3" fill="#103b2b" />
    </svg>
  );
}

export function IconeNationale(p: P) {
  return (
    <Cadre {...p}>
      <path d="M4 9.5l4-3.5 3.5 1.2L15 4l5 3.2-1.2 5 1.7 3.8-4.3 3.6-4.7-.6L7 20l-3-4.2 1.4-3.3z" />
      <circle cx="13" cy="11.5" r="1.8" fill="currentColor" stroke="none" />
    </Cadre>
  );
}

export function IconeProvince(p: P) {
  return (
    <Cadre {...p}>
      <path d="M12 21s6.5-6.2 6.5-11.2A6.5 6.5 0 0 0 5.5 9.8C5.5 14.8 12 21 12 21Z" />
      <path d="M9.6 9.2l1.6-1.4 2.3.6.4 1.9-1.2 1.7-2.1.2z" fill="currentColor" stroke="none" />
    </Cadre>
  );
}

export function IconeRegions(p: P) {
  return (
    <Cadre {...p}>
      <path d="M3.5 7.5l5-2.5 7 2.5 5-2.5v11.5l-5 2.5-7-2.5-5 2.5z" />
      <path d="M8.5 5v11.5M15.5 7.5V19" />
      <path d="M8.5 5l7 2.5V19l-7-2.5z" fill="currentColor" fillOpacity={0.35} stroke="none" />
    </Cadre>
  );
}

export function IconeSimulateur(p: P) {
  return (
    <Cadre {...p}>
      <path d="M4 7h16M4 12h16M4 17h16" strokeOpacity={0.55} />
      <circle cx="9" cy="7" r="2.1" fill="currentColor" />
      <circle cx="15.5" cy="12" r="2.1" fill="currentColor" />
      <circle cx="7" cy="17" r="2.1" fill="currentColor" />
    </Cadre>
  );
}

export function IconeMiseAJour(p: P) {
  return (
    <Cadre {...p}>
      <path d="M12 3.5v10M8 9.5l4 4 4-4" />
      <path d="M4 14.5v3.5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3.5" />
      <rect x="7" y="16.5" width="10" height="1.6" rx=".8" fill="currentColor" stroke="none" />
    </Cadre>
  );
}

export function IconeGuide(p: P) {
  return (
    <Cadre {...p}>
      <path d="M4 5.5c2.8-1 5.5-.8 8 1 2.5-1.8 5.2-2 8-1v13c-2.8-1-5.5-.8-8 1-2.5-1.8-5.2-2-8-1z" />
      <path d="M12 6.5v13" />
      <path d="M14.5 10l3-.8M14.5 13l3-.8" />
    </Cadre>
  );
}

export function IconeAlerte(p: P) {
  return (
    <Cadre {...p}>
      <path d="M12 3.5l9 15.5H3z" />
      <path d="M12 9.5v4.5" />
      <circle cx="12" cy="16.6" r="1.1" fill="currentColor" stroke="none" />
    </Cadre>
  );
}

export function IconeTableur(p: P) {
  return (
    <Cadre {...p}>
      <rect x="4" y="4.5" width="16" height="15" rx="2" />
      <path d="M4 9.5h16M4 14.5h16M10 9.5v10" />
    </Cadre>
  );
}

export function IconeRapport(p: P) {
  return (
    <Cadre {...p}>
      <path d="M6 3.5h8.5l3.5 3.5v13.5H6z" />
      <path d="M14.5 3.5V7H18" />
      <rect x="8.5" y="13" width="1.8" height="4.5" fill="currentColor" stroke="none" />
      <rect x="11.2" y="10.5" width="1.8" height="7" fill="currentColor" stroke="none" />
      <rect x="13.9" y="12" width="1.8" height="5.5" fill="currentColor" stroke="none" />
    </Cadre>
  );
}

export function IconeLecture({ taille = 16 }: P) {
  return (
    <svg width={taille} height={taille} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" />
    </svg>
  );
}

export function IconePause({ taille = 16 }: P) {
  return (
    <svg width={taille} height={taille} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="6.5" y="5.5" width="4" height="13" rx="1" fill="currentColor" />
      <rect x="13.5" y="5.5" width="4" height="13" rx="1" fill="currentColor" />
    </svg>
  );
}

export function IconeFermer(p: P) {
  return (
    <Cadre {...p}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Cadre>
  );
}
