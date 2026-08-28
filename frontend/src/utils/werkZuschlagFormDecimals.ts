import {
  loadStammdatenDecimalFields,
  submitStammdatenDecimalFields,
} from "./stammdatenFormDecimals";

export const WERK_ZUSCHLAG_PERCENT_FIELDS = ["satz_prozent"] as const;

export function loadWerkZuschlagFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, string | number | boolean> {
  return loadStammdatenDecimalFields(values, WERK_ZUSCHLAG_PERCENT_FIELDS);
}

export function submitWerkZuschlagFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, unknown> {
  return submitStammdatenDecimalFields(values, {
    percentFields: WERK_ZUSCHLAG_PERCENT_FIELDS,
  });
}
