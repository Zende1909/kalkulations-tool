/**
 * Gemeinsame Load/Submit-Transformation für Stammdaten-Formulare (StammdatenGrid).
 */

import {
  coerceFormDecimal,
  formatDecimalForInputDe,
  parsePercentPointsInput,
} from "./decimalInput";

export function loadStammdatenDecimalFields(
  values: Record<string, string | number | boolean>,
  decimalFields: readonly string[],
): Record<string, string | number | boolean> {
  const next = { ...values };
  for (const key of decimalFields) {
    const raw = next[key];
    if (raw === "" || raw == null) continue;
    if (typeof raw === "string") continue;
    if (typeof raw === "number" && Number.isFinite(raw)) {
      next[key] = formatDecimalForInputDe(raw);
    }
  }
  return next;
}

export function submitStammdatenDecimalFields(
  values: Record<string, string | number | boolean>,
  options: {
    decimalFields?: readonly string[];
    percentFields?: readonly string[];
    integerFields?: readonly string[];
    decimalExample?: string;
  },
): Record<string, unknown> {
  const payload: Record<string, unknown> = { ...values };
  const example = options.decimalExample ?? "0,10 oder 0.10";

  for (const key of options.decimalFields ?? []) {
    const raw = values[key];
    if (raw === "" || raw == null) {
      payload[key] = null;
      continue;
    }
    payload[key] = coerceFormDecimal(raw, example);
  }

  for (const key of options.percentFields ?? []) {
    const raw = values[key];
    if (raw === "" || raw == null) {
      payload[key] = null;
      continue;
    }
    payload[key] = parsePercentPointsInput(String(raw));
  }

  for (const key of options.integerFields ?? []) {
    const raw = values[key];
    if (raw === "" || raw == null) {
      payload[key] = null;
      continue;
    }
    const parsed = coerceFormDecimal(raw, "1 oder 2");
    if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
      throw new Error(`„${String(raw)}“ ist keine ganze Zahl.`);
    }
    payload[key] = parsed;
  }

  return payload;
}
