/** Formatierung für Business-Case-Anzeige (de-DE, zwei Nachkommastellen). */

export function formatEuro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

export function formatCost(value: number | null | undefined, hasCost = true): string {
  if (!hasCost || value == null || Number.isNaN(value)) return "nicht hinterlegt";
  return formatEuro(value);
}

export function formatManualPrice(
  value: number | null | undefined,
  hasManual: boolean,
): string {
  if (!hasManual || value == null || Number.isNaN(value)) return "nicht hinterlegt";
  return formatEuro(value);
}

export function formatMarginEuro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return formatEuro(value);
}

export function formatMarginPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  const rounded = Math.round(value * 100) / 100;
  return `${rounded.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %`;
}

export function formatMarginWithPercent(
  amount: number | null | undefined,
  percent: number | null | undefined,
): string {
  const euroPart = formatMarginEuro(amount);
  const pctPart = formatMarginPercent(percent);
  if (euroPart === "–" && pctPart === "–") return "–";
  if (pctPart === "–") return euroPart;
  if (euroPart === "–") return pctPart;
  return `${euroPart} (${pctPart})`;
}

export function marginClass(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "";
  return value < 0 ? "text-red-700" : "";
}

export function formatRevenueEuro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  const whole = Math.round(value);
  return `${whole.toLocaleString("de-DE", { maximumFractionDigits: 0 })} €`;
}

export function formatInteger(value: number | null | undefined): string {
  if (value == null) return "–";
  return value.toLocaleString("de-DE");
}
