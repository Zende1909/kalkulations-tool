import {
  loadStammdatenDecimalFields,
  submitStammdatenDecimalFields,
} from "./stammdatenFormDecimals";

export const ZUSCHLAGSSATZ_PERCENT_FIELDS = ["satz_prozent"] as const;

export function loadZuschlagssatzFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, string | number | boolean> {
  return loadStammdatenDecimalFields(values, ZUSCHLAGSSATZ_PERCENT_FIELDS);
}

export function submitZuschlagssatzFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, unknown> {
  return submitStammdatenDecimalFields(values, {
    percentFields: ZUSCHLAGSSATZ_PERCENT_FIELDS,
  });
}
