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

export type RevenueCurrencyScale = "eur" | "keur" | "meur";

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

/** Summe der angezeigten Jahresumsätze (bestehende Jahreswerte, keine neue Formel). */
export function sumDisplayRevenue(points: RevenueChartPoint[]): number | null {
  const values = points
    .map((p) => p.display_revenue)
    .filter((v): v is number => v != null && Number.isFinite(v));
  if (values.length === 0) return null;
  return values.reduce((sum, v) => sum + v, 0);
}

export function revenuePeriodLabel(points: RevenueChartPoint[]): string | null {
  if (points.length === 0) return null;
  const years = points.map((p) => p.calendar_year);
  const min = Math.min(...years);
  const max = Math.max(...years);
  return min === max ? String(min) : `${min}–${max}`;
}

export function chooseRevenueScale(values: Array<number | null | undefined>): RevenueCurrencyScale {
  const finite = values.filter((v): v is number => v != null && Number.isFinite(v));
  if (finite.length === 0) return "eur";
  const maxAbs = Math.max(...finite.map((v) => Math.abs(v)));
  if (maxAbs >= 1_000_000) return "meur";
  if (maxAbs >= 10_000) return "keur";
  return "eur";
}

export function formatRevenueOnScale(
  value: number | null | undefined,
  scale: RevenueCurrencyScale,
  opts: { compact?: boolean } = {},
): string {
  if (value == null || !Number.isFinite(value)) return "–";
  const compact = opts.compact ?? false;
  if (scale === "meur") {
    return `${(value / 1_000_000).toLocaleString("de-DE", {
      minimumFractionDigits: compact ? 0 : 2,
      maximumFractionDigits: 2,
    })} Mio. €`;
  }
  if (scale === "keur") {
    return `${(value / 1_000).toLocaleString("de-DE", {
      minimumFractionDigits: 0,
      maximumFractionDigits: compact ? 0 : 1,
    })} k€`;
  }
  return `${Math.round(value).toLocaleString("de-DE")} €`;
}

/** @deprecated Prefer formatRevenueOnScale with a shared scale. */
export function formatChartCurrency(value: number | null | undefined): string {
  return formatRevenueOnScale(value, chooseRevenueScale([value]));
}
