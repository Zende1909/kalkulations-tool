/**
 * Maschinen-Formular: absolute Dezimalwerte (Verbräuche, Fläche, …)
 * ohne Prozentumrechnung. Readonly-Stundensatz wird nicht mitgeschickt.
 */

import { formatDecimalForInput, parseDecimalInput } from "./decimalInput";

/** Editierbare numerische Maschinenfelder (Float laut Schema). */
export const MASCHINE_NUMERIC_FIELDS = [
  "schliesskraft_t",
  "investment",
  "flaeche_sqm",
  "stromverbrauch_kwh_h",
  "druckluftverbrauch_m3_h",
  "kuehlwasserverbrauch_m3_h",
  "setup_zeit_min",
  "setup_mitarbeiter",
] as const;

const READONLY_RATE_FIELDS = [
  "stundensatz",
  "stundensatz_source",
  "source_currency",
] as const;

export function coerceFormDecimal(
  raw: string | number | boolean | null | undefined,
): number | null {
  if (raw === "" || raw == null) return null;
  if (typeof raw === "boolean") {
    throw new Error("Erwartete Zahl, bool erhalten");
  }
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  const parsed = parseDecimalInput(String(raw));
  if (typeof parsed === "number" && Number.isFinite(parsed)) return parsed;
  throw new Error(
    `Ungültige Zahl „${String(raw)}“ – bitte z. B. 44,1 oder 44.1 eingeben`,
  );
}

export function loadMaschineFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, string | number | boolean> {
  const next = { ...values };
  for (const key of MASCHINE_NUMERIC_FIELDS) {
    const raw = next[key];
    if (raw === "" || raw == null) continue;
    if (typeof raw === "string") continue;
    if (typeof raw === "number" && Number.isFinite(raw)) {
      next[key] = formatDecimalForInput(raw);
    }
  }
  for (const key of READONLY_RATE_FIELDS) {
    const raw = next[key];
    if (typeof raw === "number" && Number.isFinite(raw)) {
      next[key] = formatDecimalForInput(raw);
    }
  }
  return next;
}

/**
 * Baut die API-Payload: Dezimalstrings → number, leere Optionals → null,
 * berechnete Stundensatzfelder werden entfernt.
 */
export function submitMaschineFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, unknown> {
  const {
    stundensatz: _s,
    stundensatz_source: _ss,
    source_currency: _sc,
    ...rest
  } = values;

  const payload: Record<string, unknown> = { ...rest };
  const werkRaw = values.werk_id;
  payload.werk_id =
    werkRaw === "" || werkRaw == null ? null : Number(werkRaw);

  for (const key of MASCHINE_NUMERIC_FIELDS) {
    const raw = values[key];
    if (raw === "" || raw == null) {
      payload[key] = null;
      continue;
    }
    payload[key] = coerceFormDecimal(raw);
  }

  if (typeof values.aktiv === "boolean") {
    payload.aktiv = values.aktiv;
  }

  return payload;
}
