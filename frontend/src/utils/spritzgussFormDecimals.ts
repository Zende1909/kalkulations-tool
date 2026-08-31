import type { SpritzgussFormData } from "../types/spritzguss";
import {
  coerceFormDecimal,
  formatDecimalForInputDe,
  parsePercentPointsInput,
  PercentPointsParseError,
} from "./decimalInput";

/** Absolute Dezimalwerte (Preise, Gewichte, Zeiten, Sätze). */
export const SPRITZGuss_DECIMAL_FIELDS = [
  "schussgewicht_g",
  "teilegewicht_netto_g",
  "materialpreis_pro_kg",
  "zykluszeit_s",
  "maschinenstundensatz",
  "lohnstundensatz",
  "setup_zeit_min",
  "setup_maschinenstundensatz",
  "setup_lohnstundensatz",
  "setup_mitarbeiter",
  "maschinen_groesse_breite_mm",
  "maschinen_groesse_laenge_mm",
  "maschinen_groesse_proj_flaeche_mm2",
] as const;

/** Prozentpunkte (nicht Bruchanteil). */
export const SPRITZGuss_PERCENT_FIELDS = [
  "ausschussquote_pct",
  "maschinen_groesse_oeffnungen_pct",
  "maschinen_groesse_schwindung_pct",
] as const;

export const SPRITZGuss_INTEGER_FIELDS = ["kavitaeten", "losgroesse_manuell"] as const;

export type SpritzgussDecimalFieldKey =
  | (typeof SPRITZGuss_DECIMAL_FIELDS)[number]
  | (typeof SPRITZGuss_PERCENT_FIELDS)[number]
  | (typeof SPRITZGuss_INTEGER_FIELDS)[number];

const ALL_RAW_FIELDS: readonly SpritzgussDecimalFieldKey[] = [
  ...SPRITZGuss_DECIMAL_FIELDS,
  ...SPRITZGuss_PERCENT_FIELDS,
  ...SPRITZGuss_INTEGER_FIELDS,
];

export function loadSpritzgussDecimalRaw(
  form: Pick<SpritzgussFormData, SpritzgussDecimalFieldKey>,
): Record<string, string> {
  const raw: Record<string, string> = {};
  for (const key of ALL_RAW_FIELDS) {
    const value = form[key];
    if (value == null) {
      raw[key] = "";
      continue;
    }
    raw[key] = formatDecimalForInputDe(value);
  }
  return raw;
}

export function parseSpritzgussDecimalFields(
  decimalRaw: Record<string, string>,
  form: SpritzgussFormData,
): SpritzgussFormData {
  const next = { ...form };

  for (const key of SPRITZGuss_DECIMAL_FIELDS) {
    const text = decimalRaw[key] ?? (form[key] == null ? "" : formatDecimalForInputDe(form[key]));
    if (text.trim() === "" && key.startsWith("maschinen_groesse_")) {
      (next as unknown as Record<string, number | null>)[key] = null;
      continue;
    }
    const parsed = coerceFormDecimal(text, "2,10 oder 2.10");
    (next as unknown as Record<string, number | null>)[key] = parsed;
  }

  for (const key of SPRITZGuss_PERCENT_FIELDS) {
    const text = decimalRaw[key] ?? (form[key] == null ? "" : formatDecimalForInputDe(form[key]));
    if (text.trim() === "" && key.startsWith("maschinen_groesse_")) {
      (next as unknown as Record<string, number | null>)[key] = null;
      continue;
    }
    (next as unknown as Record<string, number | null>)[key] = parsePercentPointsInput(text);
  }

  for (const key of SPRITZGuss_INTEGER_FIELDS) {
    const text = (decimalRaw[key] ?? formatDecimalForInputDe(form[key] ?? "")).trim();
    if (text === "") {
      if (key === "kavitaeten") {
        next.kavitaeten = 1;
      } else {
        next.losgroesse_manuell = null;
      }
      continue;
    }
    const parsed = coerceFormDecimal(text, "1");
    if (parsed == null || !Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < 1) {
      throw new PercentPointsParseError(
        key === "kavitaeten"
          ? "Kavitäten müssen eine positive ganze Zahl sein."
          : "Losgröße manuell muss eine positive ganze Zahl sein.",
      );
    }
    if (key === "kavitaeten") {
      next.kavitaeten = parsed;
    } else {
      next.losgroesse_manuell = parsed;
    }
  }

  return next;
}
