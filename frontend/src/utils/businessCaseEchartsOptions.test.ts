import { describe, expect, it } from "vitest";

import {
  buildProfitabilityGaugeOption,
  buildRevenueBarOption,
  sanitizeChartNumber,
} from "./businessCaseEchartsOptions";
import { buildRevenueChartPoints } from "./businessCaseRevenueChart";

describe("businessCaseEchartsOptions", () => {
  it("builds an EBIT/ROI gauge option with clamped pointer value", () => {
    const option = buildProfitabilityGaugeOption(31);
    expect(option).not.toBeNull();
    const series = (option?.series as Array<Record<string, unknown>>)[0];
    expect(series.type).toBe("gauge");
    expect(series.min).toBe(0);
    expect(series.max).toBe(25);
    expect(series.detail).toEqual({ show: false });
    expect(series.title).toEqual({ show: false });
    expect((series.data as Array<{ value: number }>)[0].value).toBe(25);
  });

  it("clamps negative values to 0 for the needle", () => {
    const option = buildProfitabilityGaugeOption(-4);
    const series = (option?.series as Array<Record<string, unknown>>)[0];
    expect((series.data as Array<{ value: number }>)[0].value).toBe(0);
  });

  it("uses orange band start at 5 % and green at 9 %", () => {
    const option = buildProfitabilityGaugeOption(5);
    const series = (option?.series as Array<Record<string, unknown>>)[0];
    const colors = (series.axisLine as { lineStyle: { color: Array<[number, string]> } }).lineStyle
      .color;
    expect(colors[0][0]).toBeCloseTo(5 / 25);
    expect(colors[0][1]).toBe("#DC2626");
    expect(colors[1][0]).toBeCloseTo(9 / 25);
    expect(colors[1][1]).toBe("#D97706");
    expect(colors[2][1]).toBe("#16A34A");
  });

  it("returns null for unavailable values", () => {
    expect(buildProfitabilityGaugeOption(null)).toBeNull();
    expect(buildProfitabilityGaugeOption(Number.NaN)).toBeNull();
    expect(buildProfitabilityGaugeOption(Number.POSITIVE_INFINITY)).toBeNull();
  });

  it("sanitizes NaN/Infinity before chart use", () => {
    expect(sanitizeChartNumber(Number.NaN)).toBe(0);
    expect(sanitizeChartNumber(Number.POSITIVE_INFINITY)).toBe(0);
    expect(sanitizeChartNumber(12.5)).toBe(12.5);
  });

  it("builds one bar per chronological year", () => {
    const points = buildRevenueChartPoints([
      {
        calendar_year: 2028,
        project_volume: 1,
        bottom_price_revenue: null,
        actual_revenue: 300,
      },
      {
        calendar_year: 2026,
        project_volume: 1,
        bottom_price_revenue: null,
        actual_revenue: 100,
      },
    ]);
    const option = buildRevenueBarOption(points, "eur", "tatsächlich");
    const xAxis = option.xAxis as { data: string[] };
    const series = (option.series as Array<{ data: Array<{ value: number }> }>)[0];
    expect(xAxis.data).toEqual(["2026", "2028"]);
    expect(series.data.map((d) => d.value)).toEqual([100, 300]);
  });
});
