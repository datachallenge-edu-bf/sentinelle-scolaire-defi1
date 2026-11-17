import type { ReactNode } from "react";

export default function Tuile({
  icone,
  valeur,
  libelle,
  detail,
  teinte,
}: {
  icone: ReactNode;
  valeur: ReactNode;
  libelle: ReactNode;
  detail?: ReactNode;
  teinte?: string;
}) {
  return (
    <div className="tuile" style={teinte ? ({ "--teinte": teinte } as React.CSSProperties) : undefined}>
      <div className="tuile-icone">{icone}</div>
      <div style={{ minWidth: 0 }}>
        <div className="tuile-valeur">{valeur}</div>
        <div className="tuile-libelle">{libelle}</div>
        {detail ? <div className="tuile-detail">{detail}</div> : null}
      </div>
    </div>
  );
}
