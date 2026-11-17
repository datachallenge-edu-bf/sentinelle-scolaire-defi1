import type { Metadata } from "next";
import { Suspense } from "react";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import Coquille from "@/components/Coquille";

export const metadata: Metadata = {
  title: "Sentinelle Scolaire",
  description: "Cartographie et anticipation du risque de décrochage scolaire au primaire, par province du Burkina Faso.",
};

export default function Racine({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <Suspense fallback={null}>
          <Coquille>{children}</Coquille>
        </Suspense>
      </body>
    </html>
  );
}
