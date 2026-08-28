/**
 * Material-Formular: Preis/Dichte als absolute Dezimalwerte (keine %-Logik).
 */

import { coerceFormDecimal, formatDecimalForInputDe } from "./decimalInput";

export const MATERIAL_NUMERIC_FIELDS = ["preis_pro_kg", "dichte"] as const;

export function loadMaterialFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, string | number | boolean> {
  const next = { ...values };
  for (const key of MATERIAL_NUMERIC_FIELDS) {
    const raw = next[key];
    if (raw === "" || raw == null) continue;
    if (typeof raw === "string") continue;
    if (typeof raw === "number" && Number.isFinite(raw)) {
      next[key] = formatDecimalForInputDe(raw);
    }
  }
  return next;
}

export function submitMaterialFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, unknown> {
  const payload: Record<string, unknown> = { ...values };
  for (const key of MATERIAL_NUMERIC_FIELDS) {
    const raw = values[key];
    if (raw === "" || raw == null) {
      payload[key] = null;
      continue;
    }
    payload[key] = coerceFormDecimal(raw, "2,10 oder 2.10");
  }
  if (typeof values.aktiv === "boolean") {
    payload.aktiv = values.aktiv;
  }
  return payload;
}
