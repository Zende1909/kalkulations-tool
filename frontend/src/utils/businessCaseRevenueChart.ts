import type { BusinessCaseRevenueYearRow } from "../types/businessCase";

export interface RevenueChartPoint {
  calendar_year: number;
  project_volume: number;
  bottom_price_revenue: number | null;
  actual_revenue: number | null;
  /** Primär angezeigter Umsatz (tatsächlich, sonst Bottom Price). */
  display_revenue: number | null;
  series: "actual" | "bottom" | "none";
}

export function buildRevenueChartPoints(
  rows: BusinessCaseRevenueYearRow[] | null | undefined,
): RevenueChartPoint[] {
  if (!rows?.length) return [];
  return [...rows]
    .sort((a, b) => a.calendar_year - b.calendar_year)
    .map((row) => {
      const hasActual = row.actual_revenue != null && Number.isFinite(row.actual_revenue);
      const hasBottom =
        row.bottom_price_revenue != null && Number.isFinite(row.bottom_price_revenue);
      return {
        calendar_year: row.calendar_year,
        project_volume: row.project_volume,
        bottom_price_revenue: row.bottom_price_revenue,
        actual_revenue: row.actual_revenue,
        display_revenue: hasActual
          ? row.actual_revenue
          : hasBottom
            ? row.bottom_price_revenue
            : null,
        series: hasActual ? "actual" : hasBottom ? "bottom" : "none",
      };
    });
}

export function hasDisplayableRevenue(points: RevenueChartPoint[]): boolean {
  return points.some((p) => p.display_revenue != null && Number.isFinite(p.display_revenue));
}

/** Kompakte Achsen-/Tooltip-Formatierung je nach Größenordnung. */
export function formatChartCurrency(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "–";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) {
    return `${(value / 1_000_000).toLocaleString("de-DE", {
      maximumFractionDigits: 2,
    })} MEUR`;
  }
  if (abs >= 10_000) {
    return `${(value / 1_000).toLocaleString("de-DE", {
      maximumFractionDigits: 1,
    })} kEUR`;
  }
  return `${Math.round(value).toLocaleString("de-DE")} €`;
}
