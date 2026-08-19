export const STAMMDATEN_ZUSCHLAGSSATZ_TYPEN = [
  "GEMEINKOSTEN",
  "GEWINN",
  "VERSCHROTTUNG",
] as const;

export const ASSEMBLY_MARKUP_TYPEN = ["vvgk", "gewinn", "skonto"] as const;

export const ZUSCHLAGSSATZ_TYP_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "GEMEINKOSTEN", label: "GEMEINKOSTEN" },
  { value: "GEWINN", label: "GEWINN" },
  { value: "VERSCHROTTUNG", label: "VERSCHROTTUNG" },
  { value: "vvgk", label: "vvgk (Baugruppe VVGK)" },
  { value: "gewinn", label: "gewinn (Baugruppe Gewinn)" },
  { value: "skonto", label: "skonto (Baugruppe Skonto)" },
];
