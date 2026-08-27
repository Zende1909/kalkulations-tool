/**
 * Parst Zahlen inkl. deutscher Schreibweise („0,06“ / „1.234,56“).
 * Für Live-Eingabe in Formularen die Rohzeichenkette belassen und erst
 * beim Submit parsen – sonst gehen Zwischenstände wie „0,“ / „0.“ verloren.
 */
export function parseDecimalInput(raw: string): number | "" {
  const text = raw.trim().replace(/\s|\u00a0/g, "");
  if (text === "") return "";
  let normalized = text;
  if (normalized.includes(",") && normalized.includes(".")) {
    normalized = normalized.replace(/\./g, "").replace(",", ".");
  } else if (normalized.includes(",")) {
    normalized = normalized.replace(",", ".");
  }
  // Trailing Dezimaltrenner: „0.“ / „0,“ → noch tippend, als unvollständig
  if (/[.+-]$/.test(normalized) || normalized === "." || normalized === "-" || normalized === "+") {
    return Number.NaN;
  }
  const n = Number(normalized);
  return Number.isFinite(n) ? n : Number.NaN;
}

/** True, wenn die Eingabe noch kein vollständiger Zahlenwert ist (z. B. „0,“). */
export function isIncompleteDecimalInput(raw: string): boolean {
  const text = raw.trim().replace(/\s|\u00a0/g, "");
  if (text === "" || text === "-" || text === "+" || text === "." || text === ",") {
    return true;
  }
  return /^[+-]?\d*[.,]$/.test(text);
}

/**
 * Formatiert einen gespeicherten Zahlenwert für die Anzeige im Eingabefeld
 * (Punkt als Dezimaltrenner; vermeidet wissenschaftliche Notation).
 */
export function formatDecimalForInput(
  value: number | string | null | undefined,
): string {
  if (value == null || value === "") return "";
  if (typeof value === "string") return value;
  if (!Number.isFinite(value)) return "";
  const asStr = String(value);
  if (/e/i.test(asStr)) {
    return value.toFixed(10).replace(/\.?0+$/, "");
  }
  return asStr;
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

/** Wandelt Formular-Rohwerte (inkl. „2,10“) in Zahlen um; wirft bei Ungültigem. */
export function coerceFormDecimal(
  raw: string | number | boolean | null | undefined,
  example = "2,10 oder 2.10",
): number | null {
  if (raw === "" || raw == null) return null;
  if (typeof raw === "boolean") {
    throw new Error("Erwartete Zahl, bool erhalten");
  }
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  const parsed = parseDecimalInput(String(raw));
  if (typeof parsed === "number" && Number.isFinite(parsed)) return parsed;
  throw new Error(`Ungültige Zahl „${String(raw)}“ – bitte z. B. ${example} eingeben`);
}
