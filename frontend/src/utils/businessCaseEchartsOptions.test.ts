import { describe, expect, it } from "vitest";

import {
  buildProfitabilityGaugeOption,
  buildRevenueBarOption,
  sanitizeChartNumber,
} from "./businessCaseEchartsOptions";
import { buildRevenueChartPoints } from "./businessCaseRevenueChart";

function gaugeSeries(option: NonNullable<ReturnType<typeof buildProfitabilityGaugeOption>>) {
  return (option.series as Array<Record<string, unknown>>)[0];
}

describe("businessCaseEchartsOptions", () => {
  it("builds gauge geometry without title/detail/axisLabel text overlays", () => {
    const option = buildProfitabilityGaugeOption(31);
    expect(option).not.toBeNull();
    const series = gaugeSeries(option!);
    expect(series.type).toBe("gauge");
    expect(series.startAngle).toBe(180);
    expect(series.endAngle).toBe(0);
    expect(series.min).toBe(0);
    expect(series.max).toBe(25);
    expect(series.detail).toEqual({ show: false });
    expect(series.title).toEqual({ show: false });
    expect(series.axisLabel).toEqual({ show: false });
    expect(series.axisTick).toEqual({ show: false });
    expect(series.splitLine).toEqual({ show: false });
    expect((series.data as Array<{ value: number }>)[0].value).toBe(25);
  });

  it("clamps negative values to 0 for the needle without changing geometry validity", () => {
    const option = buildProfitabilityGaugeOption(-4);
    const series = gaugeSeries(option!);
    const value = (series.data as Array<{ value: number }>)[0].value;
    expect(value).toBe(0);
    expect(Number.isFinite(value)).toBe(true);
    expect(value).not.toBe(Number.NaN);
  });

  it("uses orange band start at 5 % and green at 9 %", () => {
    const option = buildProfitabilityGaugeOption(5);
    const series = gaugeSeries(option!);
    const colors = (series.axisLine as { lineStyle: { color: Array<[number, string]> } }).lineStyle
      .color;
    expect(colors).toHaveLength(3);
    expect(colors[0][0]).toBeCloseTo(5 / 25);
    expect(colors[0][1]).toBe("#DC2626");
    expect(colors[1][0]).toBeCloseTo(9 / 25);
    expect(colors[1][1]).toBe("#D97706");
    expect(colors[2][1]).toBe("#16A34A");
  });

  it("clamps needle to 25 % for values above the fixed scale", () => {
    const option = buildProfitabilityGaugeOption(37.26);
    const series = gaugeSeries(option!);
    expect(series.max).toBe(25);
    expect((series.data as Array<{ value: number }>)[0].value).toBe(25);
  });

  it("returns null for unavailable values and never emits Infinity/NaN needle data", () => {
    expect(buildProfitabilityGaugeOption(null)).toBeNull();
    expect(buildProfitabilityGaugeOption(Number.NaN)).toBeNull();
    expect(buildProfitabilityGaugeOption(Number.POSITIVE_INFINITY)).toBeNull();

    for (const value of [0, 5, 9, 12.5, 25, 37.26, 59.19, -1]) {
      const option = buildProfitabilityGaugeOption(value);
      const series = gaugeSeries(option!);
      const needle = (series.data as Array<{ value: number }>)[0].value;
      expect(Number.isFinite(needle)).toBe(true);
      expect(needle).toBeGreaterThanOrEqual(0);
      expect(needle).toBeLessThanOrEqual(25);
    }
  });

  it("sanitizes NaN/Infinity before chart use", () => {
    expect(sanitizeChartNumber(Number.NaN)).toBe(0);
    expect(sanitizeChartNumber(Number.POSITIVE_INFINITY)).toBe(0);
    expect(sanitizeChartNumber(12.5)).toBe(12.5);
  });

  it("builds one bar per chronological year with hover-only tooltip", () => {
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
    const tooltip = option.tooltip as { alwaysShowContent?: boolean; show?: boolean };
    expect(xAxis.data).toEqual(["2026", "2028"]);
    expect(series.data.map((d) => d.value)).toEqual([100, 300]);
    expect(tooltip.alwaysShowContent).toBe(false);
    expect(tooltip.show).toBe(true);
  });
});
