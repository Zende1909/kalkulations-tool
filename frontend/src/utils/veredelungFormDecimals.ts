import type { VeredelungsschrittPayload } from "../types/veredelung";
import {
  coerceFormDecimal,
  formatDecimalForInputDe,
  parsePercentPointsInput,
} from "./decimalInput";

export const VEREDELUNG_DECIMAL_FIELDS = [
  "taktzeit_s",
  "lohnstundensatz",
  "maschinenstundensatz",
  "verbrauchskosten_je_stueck",
] as const;

export const VEREDELUNG_PERCENT_FIELDS = ["ausschussquote_pct"] as const;

export function loadVeredelungDecimalRaw(
  form: Pick<
    VeredelungsschrittPayload,
    (typeof VEREDELUNG_DECIMAL_FIELDS)[number] | (typeof VEREDELUNG_PERCENT_FIELDS)[number]
  >,
): Record<string, string> {
  const raw: Record<string, string> = {};
  for (const key of [...VEREDELUNG_DECIMAL_FIELDS, ...VEREDELUNG_PERCENT_FIELDS]) {
    const value = form[key];
    if (value == null) {
      raw[key] = "";
      continue;
    }
    raw[key] = formatDecimalForInputDe(value);
  }
  return raw;
}

export function parseVeredelungDecimalFields(
  decimalRaw: Record<string, string>,
  form: VeredelungsschrittPayload,
): VeredelungsschrittPayload {
  const next = { ...form };

  for (const key of VEREDELUNG_DECIMAL_FIELDS) {
    const rawValue = form[key as keyof typeof form];
    const text =
      decimalRaw[key] ??
      (rawValue == null
        ? ""
        : formatDecimalForInputDe(rawValue as number));
    if (key === "maschinenstundensatz") {
      if (text.trim() === "") {
        next.maschinenstundensatz = null;
        continue;
      }
      next.maschinenstundensatz = coerceFormDecimal(text);
      continue;
    }
    next[key] = coerceFormDecimal(text) as VeredelungsschrittPayload[typeof key];
  }

  next.ausschussquote_pct = parsePercentPointsInput(
    decimalRaw.ausschussquote_pct ?? formatDecimalForInputDe(form.ausschussquote_pct),
  );

  return next;
}
