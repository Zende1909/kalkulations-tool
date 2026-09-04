import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const pageSrc = readFileSync(resolve(__dirname, "./BusinessCasePage.tsx"), "utf-8");
const gaugeSrc = readFileSync(
  resolve(__dirname, "../components/businessCase/ProfitabilityGauge.tsx"),
  "utf-8",
);
const chartSrc = readFileSync(
  resolve(__dirname, "../components/businessCase/RevenueDevelopmentChart.tsx"),
  "utf-8",
);
const stripSrc = readFileSync(
  resolve(__dirname, "../components/businessCase/BusinessCaseKpiStrip.tsx"),
  "utf-8",
);
const hookSrc = readFileSync(resolve(__dirname, "../hooks/useEcharts.ts"), "utf-8");

describe("Business Case dashboard charts UI", () => {
  it("binds cockpit KPI strip, revenue chart and gauges to existing fields", () => {
    expect(pageSrc).toMatch(/BusinessCaseKpiStrip/);
    expect(pageSrc).toMatch(/RevenueDevelopmentChart/);
    expect(pageSrc).toMatch(/ProfitabilityGauge|EchartsProfitabilityGauge/);
    expect(pageSrc).toMatch(/ebit_actual_total_pct/);
    expect(pageSrc).toMatch(/roi_incl_capex_actual_pct/);
    expect(pageSrc).toMatch(/revenue_by_year/);
  });

  it("uses ECharts for gauge and revenue without overlapping detail labels", () => {
    expect(gaugeSrc).toMatch(/EchartsProfitabilityGauge|buildProfitabilityGaugeOption/);
    expect(gaugeSrc).toMatch(/useEcharts/);
    expect(gaugeSrc).toMatch(/detail: \{ show: false \}|buildProfitabilityGaugeOption/);
    expect(gaugeSrc).toMatch(/aria-label/);
    expect(gaugeSrc).toMatch(/über Skala|Der Zeiger ist am oberen Skalenende begrenzt/);
    expect(chartSrc).toMatch(/buildRevenueBarOption|useEcharts/);
    expect(chartSrc).not.toMatch(/recharts/);
    expect(chartSrc).toMatch(/sr-only/);
  });

  it("disposes ECharts on unmount and observes resize", () => {
    expect(hookSrc).toMatch(/ResizeObserver/);
    expect(hookSrc).toMatch(/dispose\(/);
    expect(hookSrc).toMatch(/prefers-reduced-motion/);
  });

  it("shows KPI strip values from existing Business Case results", () => {
    expect(stripSrc).toMatch(/Gesamtumsatz/);
    expect(stripSrc).toMatch(/sumDisplayRevenue/);
    expect(stripSrc).toMatch(/formatPercentOrDash\(ebitPct\)/);
    expect(stripSrc).toMatch(/Zeitraum/);
  });
});
