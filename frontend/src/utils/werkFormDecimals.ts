/**
 * Werk-Formular: absolute Dezimalpreise vs. UI-% für Kapitalkostensätze.
 * Keine %-Umwandlung für Strom-/Druckluft-/Kühlwasserpreis oder Space-Satz.
 */

import {
  WERK_RATE_FRACTION_FIELDS,
  formatDecimalForInput,
  fractionToUiPercent,
  parseDecimalInput,
  uiPercentToFraction,
} from "./decimalInput";

const ABSOLUTE_DECIMAL_FIELDS = [
  "fx_to_eur",
  "stunden_pro_schicht",
  "oee",
  "space_cost_satz_pro_sqm_jahr",
  "strompreis",
  "druckluftpreis",
  "kuehlwasserpreis",
  "arbeitstage_pro_jahr",
  "schichten_pro_tag",
  "abschreibungsdauer_jahre",
] as const;

export function loadWerkFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, string | number | boolean> {
  const next = { ...values };
  for (const key of WERK_RATE_FRACTION_FIELDS) {
    const raw = next[key];
    if (raw === "" || raw == null) {
      next[key] = "";
      continue;
    }
    const num = typeof raw === "number" ? raw : Number(raw);
    if (!Number.isFinite(num)) continue;
    const ui = fractionToUiPercent(num);
    next[key] = ui == null ? "" : formatDecimalForInput(ui);
  }
  for (const key of ABSOLUTE_DECIMAL_FIELDS) {
    const raw = next[key];
    if (raw === "" || raw == null) continue;
    if (typeof raw === "string") continue;
    if (typeof raw === "number" && Number.isFinite(raw)) {
      next[key] = formatDecimalForInput(raw);
    }
  }
  return next;
}

export function submitWerkFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, unknown> {
  const numericKeys = [
    ...ABSOLUTE_DECIMAL_FIELDS,
    ...WERK_RATE_FRACTION_FIELDS,
  ] as const;

  const payload: Record<string, unknown> = { ...values };
  const landRaw = values.land_id;
  payload.land_id = landRaw === "" || landRaw == null ? null : Number(landRaw);

  for (const key of numericKeys) {
    const raw = values[key];
    if (raw === "" || raw == null) {
      payload[key] = null;
      continue;
    }
    let num: number;
    if (typeof raw === "number" && Number.isFinite(raw)) {
      num = raw;
    } else {
      const parsed = parseDecimalInput(String(raw));
      num = typeof parsed === "number" ? parsed : Number.NaN;
    }
    if (!Number.isFinite(num)) {
      payload[key] = raw;
      continue;
    }
    if ((WERK_RATE_FRACTION_FIELDS as readonly string[]).includes(key)) {
      if (num < 0 || num > 100) {
        payload[key] = num;
      } else {
        payload[key] = uiPercentToFraction(num);
      }
    } else {
      payload[key] = num;
    }
  }
  return payload;
}
