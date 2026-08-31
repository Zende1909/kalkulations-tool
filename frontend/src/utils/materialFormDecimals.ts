/**
 * Material-Formular: Preis/Dichte als absolute Dezimalwerte (keine %-Logik).
 */

import { coerceFormDecimal, formatDecimalForInputDe } from "./decimalInput";

export const MATERIAL_NUMERIC_FIELDS = ["preis_pro_kg", "dichte", "injection_pressure_kg_cm2"] as const;

/** Thermische Kennwerte für die Kühlzeit – optional, leer bleibt leer. */
export const MATERIAL_THERMIK_FIELDS = [
  "schmelzdichte_kg_m3",
  "waermekapazitaet_j_kg_k",
  "waermeleitfaehigkeit_w_m_k",
  "werkzeugtemperatur_c",
  "schmelzetemperatur_c",
  "entformungstemperatur_c",
] as const;

export function loadMaterialFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, string | number | boolean> {
  const next = { ...values };
  if (next.materialgruppe == null) {
    next.materialgruppe = "";
  }
  for (const key of [...MATERIAL_NUMERIC_FIELDS, ...MATERIAL_THERMIK_FIELDS]) {
    const raw = next[key];
    if (raw == null) {
      next[key] = "";
      continue;
    }
    if (raw === "") continue;
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
  for (const key of MATERIAL_THERMIK_FIELDS) {
    const raw = values[key];
    payload[key] =
      raw === "" || raw == null ? null : coerceFormDecimal(raw, "0,27 oder 0.27");
  }
  if (values.materialgruppe === "") {
    payload.materialgruppe = null;
  }
  if (typeof values.aktiv === "boolean") {
    payload.aktiv = values.aktiv;
  }
  return payload;
}
