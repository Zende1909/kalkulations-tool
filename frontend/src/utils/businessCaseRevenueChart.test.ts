import { describe, expect, it } from "vitest";

import {
  buildRevenueChartPoints,
  chooseRevenueScale,
  formatChartCurrency,
  formatRevenueOnScale,
  hasDisplayableRevenue,
  revenuePeriodLabel,
  sumDisplayRevenue,
} from "./businessCaseRevenueChart";

describe("businessCaseRevenueChart", () => {
  it("creates one point per year in chronological order", () => {
    const points = buildRevenueChartPoints([
      {
        calendar_year: 2028,
        project_volume: 200,
        bottom_price_revenue: 2000,
        actual_revenue: 2400,
      },
      {
        calendar_year: 2026,
        project_volume: 100,
        bottom_price_revenue: 1000,
        actual_revenue: 1200,
      },
      {
        calendar_year: 2027,
        project_volume: 150,
        bottom_price_revenue: 1500,
        actual_revenue: 1800,
      },
    ]);
    expect(points.map((p) => p.calendar_year)).toEqual([2026, 2027, 2028]);
    expect(points).toHaveLength(3);
    expect(points[0].display_revenue).toBe(1200);
    expect(points[0].series).toBe("actual");
  });

  it("falls back to bottom price when actual revenue is missing", () => {
    const points = buildRevenueChartPoints([
      {
        calendar_year: 2026,
        project_volume: 100,
        bottom_price_revenue: 900,
        actual_revenue: null,
      },
    ]);
    expect(points[0].display_revenue).toBe(900);
    expect(points[0].series).toBe("bottom");
  });

  it("sums yearly revenues and formats the period", () => {
    const points = buildRevenueChartPoints([
      {
        calendar_year: 2028,
        project_volume: 1,
        bottom_price_revenue: null,
        actual_revenue: 200,
      },
      {
        calendar_year: 2026,
        project_volume: 1,
        bottom_price_revenue: null,
        actual_revenue: 100,
      },
    ]);
    expect(sumDisplayRevenue(points)).toBe(300);
    expect(revenuePeriodLabel(points)).toBe("2026–2028");
  });

  it("uses one shared currency scale for all chart values", () => {
    expect(chooseRevenueScale([2_500_000, 750_000, 0])).toBe("meur");
    expect(formatRevenueOnScale(2_500_000, "meur")).toMatch(/Mio\. €/);
    expect(formatRevenueOnScale(750_000, "meur")).toMatch(/Mio\. €/);
    expect(formatRevenueOnScale(0, "meur")).toMatch(/Mio\. €/);
    expect(chooseRevenueScale([28000, 12000])).toBe("keur");
  });

  it("detects empty revenue data", () => {
    expect(hasDisplayableRevenue([])).toBe(false);
    expect(
      hasDisplayableRevenue([
        {
          calendar_year: 2026,
          project_volume: 0,
          bottom_price_revenue: null,
          actual_revenue: null,
          display_revenue: null,
          series: "none",
        },
      ]),
    ).toBe(false);
    expect(
      hasDisplayableRevenue([
        {
          calendar_year: 2026,
          project_volume: 10,
          bottom_price_revenue: 100,
          actual_revenue: 120,
          display_revenue: 120,
          series: "actual",
        },
      ]),
    ).toBe(true);
  });

  it("keeps legacy formatChartCurrency helper working", () => {
    expect(formatChartCurrency(28000)).toMatch(/k€/);
    expect(formatChartCurrency(2_500_000)).toMatch(/Mio/);
    expect(formatChartCurrency(850)).toBe("850 €");
  });
});
