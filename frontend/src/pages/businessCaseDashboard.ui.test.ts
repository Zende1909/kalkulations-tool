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
const optionsSrc = readFileSync(
  resolve(__dirname, "../utils/businessCaseEchartsOptions.ts"),
  "utf-8",
);

describe("Business Case dashboard charts UI", () => {
  it("binds cockpit KPI strip, revenue chart and gauges to existing fields", () => {
    expect(pageSrc).toMatch(/BusinessCaseKpiStrip/);
    expect(pageSrc).toMatch(/RevenueDevelopmentChart/);
    expect(pageSrc).toMatch(/ProfitabilityGauge/);
    expect(pageSrc).toMatch(/ebit_actual_total_pct/);
    expect(pageSrc).toMatch(/roi_incl_capex_actual_pct/);
    expect(pageSrc).toMatch(/revenue_by_year/);
    expect(pageSrc).toMatch(/businessCaseXlsxUrl|exportExcel/);
    expect(pageSrc).toMatch(/businessCasePdfUrl|exportPdf/);
  });

  it("uses one reusable gauge component for EBIT and ROI", () => {
    expect(gaugeSrc).toMatch(/export function EchartsProfitabilityGauge/);
    expect(gaugeSrc).toMatch(/export const ProfitabilityGauge = EchartsProfitabilityGauge/);
    const gaugeUsages = pageSrc.match(/<ProfitabilityGauge/g) ?? [];
    expect(gaugeUsages.length).toBe(2);
  });

  it("keeps ECharts geometry free of duplicate percent/detail text", () => {
    expect(optionsSrc).toMatch(/detail:\s*\{\s*show:\s*false\s*\}/);
    expect(optionsSrc).toMatch(/title:\s*\{\s*show:\s*false\s*\}/);
    expect(optionsSrc).toMatch(/axisLabel:\s*\{\s*show:\s*false\s*\}/);
    expect(gaugeSrc).toMatch(/data-testid="gauge-value"/);
    expect(gaugeSrc).toMatch(/data-testid="gauge-label"/);
    expect(gaugeSrc).toMatch(/data-testid="gauge-status"/);
    expect(gaugeSrc).toMatch(/className="gauge-value/);
    expect(gaugeSrc).not.toMatch(/detail:\s*\{[^}]*formatter/);
  });

  it("renders value, label and status as separate HTML outside the chart canvas", () => {
    expect(gaugeSrc).toMatch(/gauge-chart-area/);
    expect(gaugeSrc).toMatch(/gauge-value-area/);
    expect(gaugeSrc).toMatch(/GaugeChartGeometry/);
    expect(gaugeSrc).toMatch(/overflow-visible/);
    expect(gaugeSrc).toMatch(/min-w-0/);
    expect(gaugeSrc).not.toMatch(/-mt-|absolute.*(gauge-value|displayValue)/);
  });

  it("shows above-scale note only for values over 25 % and keeps accessibility label", () => {
    expect(gaugeSrc).toMatch(/state\.isAboveScale/);
    expect(gaugeSrc).toMatch(/Der Zeiger ist am oberen Skalenende begrenzt/);
    expect(gaugeSrc).toMatch(/aria-label=\{ariaLabel\}/);
    expect(gaugeSrc).toMatch(/Status \$\{state\.zoneLabel\}/);
    expect(gaugeSrc).toMatch(/gauge-scale-labels/);
    expect(gaugeSrc).toMatch(/GAUGE_SCALE_MARKS/);
  });

  it("uses equal-height card layout with responsive legend and stacked mobile gauges", () => {
    expect(gaugeSrc).toMatch(/profitability-card/);
    expect(gaugeSrc).toMatch(/h-full/);
    expect(gaugeSrc).toMatch(/gauge-legend/);
    expect(gaugeSrc).toMatch(/sm:grid-cols-3/);
    expect(pageSrc).toMatch(/items-stretch/);
    expect(pageSrc).toMatch(/grid-cols-1[\s\S]*lg:grid-cols-2/);
  });

  it("keeps revenue chart accessible and updates from the same Business Case payload", () => {
    expect(chartSrc).toMatch(/buildRevenueBarOption|useEcharts/);
    expect(chartSrc).not.toMatch(/recharts/);
    expect(chartSrc).toMatch(/sr-only/);
    expect(chartSrc).toMatch(/min-w-0/);
    expect(pageSrc).toMatch(/RevenueDevelopmentChart rows=\{data\.revenue_by_year/);
    expect(pageSrc).toMatch(/BusinessCaseKpiStrip[\s\S]*revenueByYear=\{data\.revenue_by_year/);
  });

  it("disposes ECharts on unmount and observes resize", () => {
    expect(hookSrc).toMatch(/ResizeObserver/);
    expect(hookSrc).toMatch(/dispose\(/);
    expect(hookSrc).toMatch(/prefers-reduced-motion/);
    expect(hookSrc).toMatch(/useRef/);
  });

  it("shows KPI strip values from existing Business Case results", () => {
    expect(stripSrc).toMatch(/Gesamtumsatz/);
    expect(stripSrc).toMatch(/sumDisplayRevenue/);
    expect(stripSrc).toMatch(/formatPercentOrDash\(ebitPct\)/);
    expect(stripSrc).toMatch(/Zeitraum/);
  });
});
