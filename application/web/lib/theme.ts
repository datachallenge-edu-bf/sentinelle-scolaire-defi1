/** Réglages communs des graphiques : axes et grille discrets, texte dans les encres du thème. */
export const TEXTE = "#b4c0d4";
export const TEXTE_DISCRET = "#8293ad";
export const TEXTE_FORT = "#e8eef8";
export const GRILLE = "rgba(130, 147, 173, 0.16)";
export const SURFACE = "#111a2b";
export const AXE_LIGNE = "#33476a";

export const INFO_BULLE = {
  backgroundColor: "rgba(10, 17, 31, 0.97)",
  borderColor: "#33476a",
  borderWidth: 1,
  textStyle: { color: "#e8eef8", fontSize: 12.5 },
  extraCssText: "border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.35);",
};

export function axe(nom?: string, grille = true) {
  return {
    name: nom,
    nameTextStyle: { color: TEXTE_DISCRET, fontSize: 12 },
    axisLine: { lineStyle: { color: AXE_LIGNE } },
    axisTick: { show: false },
    axisLabel: { color: TEXTE, fontSize: 12 },
    splitLine: { show: grille, lineStyle: { color: GRILLE } },
  };
}
