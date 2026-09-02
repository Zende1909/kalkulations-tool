import type { ICellRendererParams, ValueFormatterParams } from "ag-grid-community";

import { booleanActiveBadge } from "./StatusBadge";

export function formatDecimal(value: unknown, fractionDigits = 2): string {
  if (value == null || value === "") return "–";
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return String(value);
  return num.toLocaleString("de-DE", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

export function decimalValueFormatter(fractionDigits = 2) {
  return (params: ValueFormatterParams) => formatDecimal(params.value, fractionDigits);
}

export function activeStatusCellRenderer(params: ICellRendererParams) {
  return booleanActiveBadge(Boolean(params.value));
}
