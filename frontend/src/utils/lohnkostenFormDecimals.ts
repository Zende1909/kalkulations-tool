import {
  loadStammdatenDecimalFields,
  submitStammdatenDecimalFields,
} from "./stammdatenFormDecimals";

export const LOHNKOSTEN_DECIMAL_FIELDS = ["kosten_pro_stunde", "source_rate"] as const;
export const LOHNKOSTEN_INTEGER_FIELDS = ["werk_id"] as const;

export function loadLohnkostenFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, string | number | boolean> {
  return loadStammdatenDecimalFields(values, LOHNKOSTEN_DECIMAL_FIELDS);
}

export function submitLohnkostenFormValues(
  values: Record<string, string | number | boolean>,
): Record<string, unknown> {
  return submitStammdatenDecimalFields(values, {
    decimalFields: LOHNKOSTEN_DECIMAL_FIELDS,
    integerFields: LOHNKOSTEN_INTEGER_FIELDS,
  });
}
