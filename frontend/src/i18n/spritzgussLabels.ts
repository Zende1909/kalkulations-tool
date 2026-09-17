import type { TranslateParams } from "./translate";

/** Translator signature matching useT(). */
export type TFn = (key: string, params?: TranslateParams, fallback?: string) => string;

export const ERGEBNISUEBERSICHT_DEF: Array<{
  key: string;
  labelKey: string;
  emphasis?: "primary" | "secondary";
  hideZero?: boolean;
}> = [
  { key: "materialkosten_gesamt", labelKey: "spritzguss.overview.materialInclScrapMgk" },
  { key: "maschinenkosten", labelKey: "spritzguss.overview.machineCostPerGood" },
  { key: "fertigungslohn", labelKey: "spritzguss.overview.laborPerGood" },
  { key: "setup_kosten_je_teil", labelKey: "spritzguss.overview.setupPerPart", hideZero: true },
  { key: "veredelung_gesamt", labelKey: "spritzguss.overview.finishingDirect", hideZero: true },
  { key: "fgk_basis", labelKey: "spritzguss.overview.fgkBase" },
  { key: "fertigungsgemeinkosten", labelKey: "spritzguss.overview.fgkAmountOnce" },
  { key: "gesamte_herstellkosten", labelKey: "spritzguss.overview.manufacturingCost" },
  { key: "vvgk", labelKey: "spritzguss.overview.sgaVvgk" },
  { key: "selbstkosten", labelKey: "spritzguss.overview.fullCost", emphasis: "primary" },
  { key: "gewinn", labelKey: "spritzguss.overview.profit" },
  { key: "nettoverkaufspreis_gesamt", labelKey: "spritzguss.overview.netSellingPrice" },
  { key: "skonto", labelKey: "spritzguss.overview.cashDiscount", hideZero: true },
  { key: "endpreis_je_stueck", labelKey: "spritzguss.overview.finalPricePerPc", emphasis: "secondary" },
  { key: "spritzguss_herstellkosten", labelKey: "spritzguss.overview.ofWhichMoldingHk" },
];

export const DETAIL_BLOCK_ORDER = [
  "material",
  "fertigung",
  "veredelung",
  "gemeinkosten",
  "verkaufspreis",
] as const;

export const BLOCK_LABEL_KEYS: Record<string, string> = {
  material: "spritzguss.block.material",
  fertigung: "spritzguss.block.fertigung",
  veredelung: "spritzguss.block.veredelung",
  gemeinkosten: "spritzguss.block.gemeinkosten",
  verkaufspreis: "spritzguss.block.verkaufspreis",
};

export const FIELD_LABEL_KEYS: Record<string, string> = {
  materialgewicht_kg: "spritzguss.field.materialgewicht_kg",
  materialkosten: "spritzguss.field.materialkosten",
  materialkosten_inkl_ausschuss: "spritzguss.field.materialkosten_inkl_ausschuss",
  materialausschuss_betrag: "spritzguss.field.materialausschuss_betrag",
  materialgemeinkosten: "spritzguss.field.materialgemeinkosten",
  materialkosten_gesamt: "spritzguss.field.materialkosten_gesamt",
  mgk_basis: "spritzguss.field.mgk_basis",
  mgk_pct: "spritzguss.field.mgk_pct",
  material_nominierung: "spritzguss.field.material_nominierung",
  maschinenkosten: "spritzguss.field.maschinenkosten",
  fertigungslohn: "spritzguss.field.fertigungslohn",
  fertigungsgemeinkosten: "spritzguss.field.fertigungsgemeinkosten",
  fgk_basis: "spritzguss.field.fgk_basis",
  fgk_pct: "spritzguss.field.fgk_pct",
  bruttokapazitaet_exakt: "spritzguss.field.bruttokapazitaet_exakt",
  bruttokapazitaet: "spritzguss.field.bruttokapazitaet",
  nettokapazitaet: "spritzguss.field.nettokapazitaet",
  setup_maschinenkosten_je_teil: "spritzguss.field.setup_maschinenkosten_je_teil",
  setup_lohnkosten_je_teil: "spritzguss.field.setup_lohnkosten_je_teil",
  setup_kosten_je_teil: "spritzguss.field.setup_kosten_je_teil",
  losgroesse: "spritzguss.field.losgroesse",
  losgroesse_modus: "spritzguss.field.losgroesse_modus",
  losgroesse_automatisch: "spritzguss.field.losgroesse_automatisch",
  losgroesse_aktiv: "spritzguss.field.losgroesse_aktiv",
  losgroesse_jahresbedarf: "spritzguss.field.losgroesse_jahresbedarf",
  produktionsintervall_arbeitstage: "spritzguss.field.produktionsintervall_arbeitstage",
  arbeitstage_pro_jahr: "spritzguss.field.arbeitstage_pro_jahr",
  losgroesse_hinweis: "spritzguss.field.losgroesse_hinweis",
  vvgk_pct: "spritzguss.field.vvgk_pct",
  gewinn_pct: "spritzguss.field.gewinn_pct",
  skonto_pct: "spritzguss.field.skonto_pct",
  vvgk_basis: "spritzguss.field.vvgk_basis",
  gewinn_basis: "spritzguss.field.gewinn_basis",
  werkzeugkostenanteil: "spritzguss.field.werkzeugkostenanteil",
  werkzeug_einmalzahlung: "spritzguss.field.werkzeug_einmalzahlung",
  herstellkosten: "spritzguss.field.herstellkosten",
  vvgk: "spritzguss.field.vvgk",
  selbstkosten: "spritzguss.field.selbstkosten",
  gewinn: "spritzguss.field.gewinn",
  nettoverkaufspreis: "spritzguss.field.nettoverkaufspreis",
  skonto: "spritzguss.field.skonto",
  verkaufspreis: "spritzguss.field.verkaufspreis",
};

export function fieldLabel(t: TFn, field: string): string {
  const key = FIELD_LABEL_KEYS[field];
  return key ? t(key) : field;
}

export function blockLabel(t: TFn, blockKey: string): string {
  const key = BLOCK_LABEL_KEYS[blockKey];
  return key ? t(key) : blockKey;
}

export function veredelungDetailLabel(
  t: TFn,
  field: string,
  selectedVeredelung: Array<{ reihenfolge: number; bezeichnung: string }>,
): string {
  if (field === "veredelung_gesamt") return t("spritzguss.field.veredelung_gesamt");
  const match = /^schritt_(\d+)$/.exec(field);
  if (!match) return field;
  const schritt = selectedVeredelung.find((s) => s.reihenfolge === Number(match[1]));
  return schritt
    ? `${schritt.bezeichnung} (€)`
    : t("spritzguss.field.veredelung_step", { n: match[1] });
}

export function entnahmeLabel(t: TFn, key: string): string {
  return t(`spritzguss.entnahme.${key}.label`);
}

export function entnahmeDesc(t: TFn, key: string): string {
  return t(`spritzguss.entnahme.${key}.desc`);
}

export function sizeClassLabel(t: TFn, key: string): string {
  return t(`spritzguss.sizeClass.${key}`);
}
