/**
 * Materialgruppen-Formular: thermische Kennwerte als absolute Dezimalwerte.
 */

import { coerceFormDecimal, formatDecimalForInputDe } from "./decimalInput";

export const MATERIALGRUPPE_NUMERIC_FIELDS = [
  "schmelzdichte_kg_m3",
  "waermekapazitaet_j_kg_k",
  "waermeleitfaehigkeit_w_m_k",
  "werkzeugtemperatur_c",
  "schmelzetemperatur_c",
  "entformungstemperatur_c",
] as const;

export function loadMaterialgruppeFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, string | number | boolean> {
  const next = { ...values };
  for (const key of MATERIALGRUPPE_NUMERIC_FIELDS) {
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

export function submitMaterialgruppeFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, unknown> {
  const payload: Record<string, unknown> = { ...values };
  for (const key of MATERIALGRUPPE_NUMERIC_FIELDS) {
    const raw = values[key];
    if (raw === "" || raw == null) {
      payload[key] = null;
      continue;
    }
    payload[key] = coerceFormDecimal(raw, "Dezimalzahl");
  }
  if (typeof values.aktiv === "boolean") {
    payload.aktiv = values.aktiv;
  }
  return payload;
}
