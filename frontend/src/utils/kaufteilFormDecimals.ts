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
  const base = submitStammdatenDecimalFields(values, {
    decimalFields: KAUFTEIL_DECIMAL_FIELDS,
    decimalExample: "0,10 oder 0.10",
  });
  const toNullableId = (key: string): number | null => {
    const raw = base[key];
    if (raw === "" || raw == null) return null;
    const n = typeof raw === "number" ? raw : Number(raw);
    return Number.isFinite(n) ? n : null;
  };
  const projectId = toNullableId("project_id");
  if (projectId == null) {
    return {
      ...base,
      customer_id: null,
      program_id: null,
      project_id: null,
      sga_override_aktiv: Boolean(base.sga_override_aktiv),
      sga_satz_manuell: base.sga_override_aktiv ? toNullableId("sga_satz_manuell") : null,
    };
  }
  return {
    ...base,
    customer_id: toNullableId("customer_id"),
    program_id: toNullableId("program_id"),
    project_id: projectId,
    sga_override_aktiv: Boolean(base.sga_override_aktiv),
    sga_satz_manuell: base.sga_override_aktiv ? toNullableId("sga_satz_manuell") : null,
  };
}
