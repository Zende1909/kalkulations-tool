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

describe("Business Case dashboard charts UI", () => {
  it("binds cockpit KPI strip, revenue chart and gauges to existing fields", () => {
    expect(pageSrc).toMatch(/BusinessCaseKpiStrip/);
    expect(pageSrc).toMatch(/RevenueDevelopmentChart/);
    expect(pageSrc).toMatch(/ProfitabilityGauge/);
    expect(pageSrc).toMatch(/ebit_actual_total_pct/);
    expect(pageSrc).toMatch(/roi_incl_capex_actual_pct/);
    expect(pageSrc).toMatch(/revenue_by_year/);
    expect(pageSrc).toMatch(/Business-Case-Dashboard/);
  });

  it("shows KPI strip values from existing Business Case results", () => {
    expect(stripSrc).toMatch(/Gesamtumsatz/);
    expect(stripSrc).toMatch(/sumDisplayRevenue/);
    expect(stripSrc).toMatch(/formatPercentOrDash\(ebitPct\)/);
    expect(stripSrc).toMatch(/formatPercentOrDash\(roiPct\)/);
    expect(stripSrc).toMatch(/Zeitraum/);
  });

  it("exposes accessibility labels and textual status on the gauge", () => {
    expect(gaugeSrc).toMatch(/aria-label/);
    expect(gaugeSrc).toMatch(/zoneLabel/);
    expect(gaugeSrc).toMatch(/nicht verfügbar/);
    expect(gaugeSrc).toMatch(/0–5 % kritisch/);
    expect(gaugeSrc).toMatch(/über Skala|Der Zeiger ist am oberen Skalenende begrenzt/);
    expect(gaugeSrc).toMatch(/marks = \[0,/);
    expect(gaugeSrc).toMatch(/GAUGE_SCALE_MAX/);
  });

  it("keeps revenue table accessible without crowding the chart", () => {
    expect(chartSrc).toMatch(/sr-only/);
    expect(chartSrc).toMatch(/Für den ausgewählten Business Case liegen noch keine Umsatzwerte vor/);
    expect(chartSrc).toMatch(/chooseRevenueScale|formatRevenueOnScale/);
    expect(chartSrc).toMatch(/Jahreswerte/);
  });
});
