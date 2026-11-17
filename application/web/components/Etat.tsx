export function Chargement() {
  return <div className="chargement">Chargement des données…</div>;
}

export function Erreur({ message }: { message: string }) {
  return (
    <div className="erreur">
      Impossible de joindre l&apos;API ({message}). Vérifiez qu&apos;elle tourne sur le port 8000.
    </div>
  );
}
