import type { SpritzgussFormData } from "../types/spritzguss";
import {
  ZYKLUSZEIT_DEFAULT_KUEHLFAKTOR,
  ZYKLUSZEIT_NEBENZEIT_DEFAULTS,
} from "../types/spritzguss";
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
  "zykluszeit_wandstaerke_mm",
  "zykluszeit_kuehlfaktor",
  "zykluszeit_nz_werkzeug_schliessen_s",
  "zykluszeit_nz_duese_anlegen_s",
  "zykluszeit_nz_einspritzen_s",
  "zykluszeit_nz_werkzeug_oeffnen_s",
  "zykluszeit_nz_auswerfen_s",
  "zykluszeit_nz_kernzug_s",
  "zykluszeit_nz_ausschrauben_s",
  "zykluszeit_nz_einlegen_s",
  "zykluszeit_nz_ausblasen_s",
] as const;

/** Prozentpunkte (nicht Bruchanteil). */
export const SPRITZGuss_PERCENT_FIELDS = [
  "ausschussquote_pct",
  "maschinen_groesse_oeffnungen_pct",
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

/** Felder, die bei leerer Eingabe `null` bleiben statt auf 0 zu fallen. */
const NULLABLE_WHEN_EMPTY = new Set<string>([
  "maschinen_groesse_breite_mm",
  "maschinen_groesse_laenge_mm",
  "maschinen_groesse_proj_flaeche_mm2",
  "maschinen_groesse_oeffnungen_pct",
  "zykluszeit_wandstaerke_mm",
]);

/** Felder, die bei leerer Eingabe auf ihren IKET-Default zurückfallen. */
const DEFAULT_WHEN_EMPTY: Record<string, number> = {
  zykluszeit_kuehlfaktor: ZYKLUSZEIT_DEFAULT_KUEHLFAKTOR,
  ...ZYKLUSZEIT_NEBENZEIT_DEFAULTS,
};

export function parseSpritzgussDecimalFields(
  decimalRaw: Record<string, string>,
  form: SpritzgussFormData,
): SpritzgussFormData {
  const next = { ...form };

  for (const key of SPRITZGuss_DECIMAL_FIELDS) {
    const text = decimalRaw[key] ?? (form[key] == null ? "" : formatDecimalForInputDe(form[key]));
    if (text.trim() === "") {
      if (NULLABLE_WHEN_EMPTY.has(key)) {
        (next as unknown as Record<string, number | null>)[key] = null;
        continue;
      }
      if (key in DEFAULT_WHEN_EMPTY) {
        (next as unknown as Record<string, number | null>)[key] = DEFAULT_WHEN_EMPTY[key];
        continue;
      }
    }
    const parsed = coerceFormDecimal(text, "2,10 oder 2.10");
    (next as unknown as Record<string, number | null>)[key] = parsed;
  }

  for (const key of SPRITZGuss_PERCENT_FIELDS) {
    const text = decimalRaw[key] ?? (form[key] == null ? "" : formatDecimalForInputDe(form[key]));
    if (text.trim() === "" && NULLABLE_WHEN_EMPTY.has(key)) {
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
