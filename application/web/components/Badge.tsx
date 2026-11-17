import type { Classe } from "@/lib/api";
import { COULEURS_CLASSES, LIBELLES_CLASSES } from "@/lib/format";

export default function Badge({ classe, texte, grand }: { classe: Classe; texte?: string; grand?: boolean }) {
  return (
    <span className={`badge${grand ? " grand" : ""}`} style={{ background: COULEURS_CLASSES[classe] }}>
      {texte ?? LIBELLES_CLASSES[classe]}
    </span>
  );
}
