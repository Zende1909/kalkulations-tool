/** Parst Zahlen inkl. deutscher Schreibweise („0,92“ / „1.234,56“). */
export function parseDecimalInput(raw: string): number | "" {
  const text = raw.trim().replace(/\s|\u00a0/g, "");
  if (text === "") return "";
  let normalized = text;
  if (normalized.includes(",") && normalized.includes(".")) {
    normalized = normalized.replace(/\./g, "").replace(",", ".");
  } else if (normalized.includes(",")) {
    normalized = normalized.replace(",", ".");
  }
  const n = Number(normalized);
  return Number.isFinite(n) ? n : Number.NaN;
}

/**
 * Werk-Kapitalkostensätze: intern Anteil (0.08), UI Prozent (8).
 * Werte > 1 gelten als Altdaten-Fehler – keine automatische ×100-Korrektur.
 */
export const WERK_RATE_FRACTION_FIELDS = [
  "zinssatz",
  "versicherungssatz",
  "instandhaltungssatz",
] as const;

export type WerkRateFractionField = (typeof WERK_RATE_FRACTION_FIELDS)[number];

export function fractionToUiPercent(fraction: number | null | undefined): number | null {
  if (fraction == null || !Number.isFinite(fraction)) return null;
  if (fraction < 0 || fraction > 1) return fraction; // Altdaten: roh anzeigen
  return fraction * 100;
}

export function uiPercentToFraction(uiPercent: number | null | undefined): number | null {
  if (uiPercent == null || !Number.isFinite(uiPercent)) return null;
  return uiPercent / 100;
}

export function formatPercentPoints(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return "–";
  return `${value.toLocaleString("de-DE", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })} %`;
}
