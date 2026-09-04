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
    expect(pageSrc).toMatch(/ebit_bottom_total_pct/);
    expect(pageSrc).toMatch(/roi_incl_capex_actual_pct/);
    expect(pageSrc).toMatch(/revenue_by_year/);
    expect(pageSrc).toMatch(/businessCaseXlsxUrl|exportExcel/);
    expect(pageSrc).toMatch(/businessCasePdfUrl|exportPdf/);
  });

  it("uses one reusable gauge for EBIT, EBIT Bottom Price and ROI", () => {
    expect(gaugeSrc).toMatch(/export function EchartsProfitabilityGauge/);
    expect(gaugeSrc).toMatch(/export const ProfitabilityGauge = EchartsProfitabilityGauge/);
    const gaugeUsages = pageSrc.match(/<ProfitabilityGauge/g) ?? [];
    expect(gaugeUsages.length).toBe(3);
    expect(pageSrc).toMatch(/data-testid="gauge-ebit"/);
    expect(pageSrc).toMatch(/data-testid="gauge-ebit-bottom"/);
    expect(pageSrc).toMatch(/data-testid="gauge-roi"/);
  });

  it("places EBIT gauges on one row and ROI with compact revenue on the next", () => {
    expect(pageSrc).toMatch(/gauge-ebit[\s\S]*gauge-ebit-bottom/);
    expect(pageSrc).toMatch(/gauge-roi[\s\S]*RevenueDevelopmentChart/);
    expect(pageSrc).toMatch(/variant="compact"/);
    expect(chartSrc).toMatch(/variant\?: "default" \| "compact"/);
  });

  it("keeps ECharts geometry free of duplicate percent/detail text", () => {
    expect(optionsSrc).toMatch(/detail:\s*\{\s*show:\s*false\s*\}/);
    expect(optionsSrc).toMatch(/title:\s*\{\s*show:\s*false\s*\}/);
    expect(optionsSrc).toMatch(/axisLabel:\s*\{\s*show:\s*false\s*\}/);
    expect(gaugeSrc).toMatch(/data-testid="gauge-value"/);
    expect(gaugeSrc).toMatch(/state\.zoneColor/);
    expect(gaugeSrc).not.toMatch(/gaugeArcLabelPosition/);
    expect(gaugeSrc).not.toMatch(/gauge-scale-labels/);
  });

  it("keeps scale ranges only in the bottom legend, not on the arc", () => {
    expect(gaugeSrc).toMatch(/gauge-legend/);
    expect(gaugeSrc).toMatch(/0–5&nbsp;%/);
    expect(gaugeSrc).toMatch(/gauge-value-area/);
    expect(gaugeSrc).toMatch(/style=\{\{ color: state\.zoneColor \}\}/);
  });

  it("shows above-scale note only for values over 25 % and keeps accessibility label", () => {
    expect(gaugeSrc).toMatch(/state\.isAboveScale/);
    expect(gaugeSrc).toMatch(/Der Zeiger ist am oberen Skalenende begrenzt/);
    expect(gaugeSrc).toMatch(/aria-label=\{ariaLabel\}/);
  });

  it("uses a compact revenue layout that fills the shared row cleanly", () => {
    expect(chartSrc).toMatch(/variant\?: "default" \| "compact"/);
    expect(chartSrc).toMatch(/gridTemplateColumns/);
    expect(chartSrc).toMatch(/min-h-\[10rem\]/);
    expect(chartSrc).not.toMatch(/grid-cols-2 gap-x-3 gap-y-1 sm:grid-cols-3/);
  });

  it("omits kritisch/beobachten/positiv wording from the color legend", () => {
    expect(gaugeSrc).toMatch(/0–5&nbsp;%/);
    expect(gaugeSrc).toMatch(/5–9&nbsp;%/);
    expect(gaugeSrc).toMatch(/9–25&nbsp;%/);
    expect(gaugeSrc).not.toMatch(/0–5&nbsp;% kritisch/);
    expect(gaugeSrc).not.toMatch(/beobachten/);
    expect(gaugeSrc).not.toMatch(/9–25&nbsp;% positiv/);
  });

  it("matches full page width like Details/Baugruppen sections", () => {
    expect(pageSrc).toMatch(
      /section className="w-full space-y-3 rounded-lg border border-slate-200/,
    );
    expect(pageSrc).not.toMatch(/max-w-6xl/);
  });

  it("uses equal-height card layout with responsive legend and stacked mobile gauges", () => {
    expect(gaugeSrc).toMatch(/profitability-card/);
    expect(gaugeSrc).toMatch(/h-full/);
    expect(gaugeSrc).toMatch(/gauge-legend/);
    expect(gaugeSrc).toMatch(/grid-cols-3/);
    expect(pageSrc).toMatch(/items-stretch/);
    expect(pageSrc).toMatch(/lg:grid-cols-2/);
  });

  it("keeps revenue chart accessible and updates from the same Business Case payload", () => {
    expect(chartSrc).toMatch(/buildRevenueBarOption|useEcharts/);
    expect(chartSrc).not.toMatch(/recharts/);
    expect(chartSrc).toMatch(/sr-only/);
    expect(chartSrc).toMatch(/min-w-0/);
    expect(pageSrc).toMatch(/RevenueDevelopmentChart[\s\S]*revenue_by_year/);
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
