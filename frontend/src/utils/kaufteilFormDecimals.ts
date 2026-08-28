import {
  loadStammdatenDecimalFields,
  submitStammdatenDecimalFields,
} from "./stammdatenFormDecimals";

export const KAUFTEIL_DECIMAL_FIELDS = ["preis"] as const;

export function loadKaufteilFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, string | number | boolean> {
  return loadStammdatenDecimalFields(values, KAUFTEIL_DECIMAL_FIELDS);
}

export function submitKaufteilFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, unknown> {
  return submitStammdatenDecimalFields(values, {
    decimalFields: KAUFTEIL_DECIMAL_FIELDS,
    decimalExample: "0,10 oder 0.10",
  });
}
