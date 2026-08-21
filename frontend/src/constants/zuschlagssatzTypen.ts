export const STAMMDATEN_ZUSCHLAGSSATZ_TYPEN = [
  "GEMEINKOSTEN",
  "GEWINN",
  "VERSCHROTTUNG",
] as const;

export const CENTRAL_MARKUP_TYPEN = [
  "mgk_kaufteil_selbst",
  "mgk_kaufteil_oem",
  "fgk",
  "vvgk",
  "gewinn",
  "skonto",
] as const;

/** @deprecated Alias – nutze CENTRAL_MARKUP_TYPEN */
export const ASSEMBLY_MARKUP_TYPEN = ["vvgk", "gewinn", "skonto"] as const;

export const ZUSCHLAGSSATZ_TYP_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "GEMEINKOSTEN", label: "GEMEINKOSTEN (Katalog)" },
  { value: "GEWINN", label: "GEWINN (Katalog)" },
  { value: "VERSCHROTTUNG", label: "VERSCHROTTUNG (Katalog)" },
  { value: "mgk_kaufteil_selbst", label: "MGK selbstnominiert (Material & Kaufteile)" },
  { value: "mgk_kaufteil_oem", label: "MGK OEM-nominiert (Material & Kaufteile)" },
  { value: "fgk", label: "FGK" },
  { value: "vvgk", label: "VVGK / SG&A" },
  { value: "gewinn", label: "Gewinn / Profit" },
  { value: "skonto", label: "Skonto" },
];
