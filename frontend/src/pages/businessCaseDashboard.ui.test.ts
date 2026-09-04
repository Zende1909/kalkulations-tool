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

describe("Business Case dashboard charts UI", () => {
  it("binds revenue chart and both gauges to existing KPI fields", () => {
    expect(pageSrc).toMatch(/RevenueDevelopmentChart/);
    expect(pageSrc).toMatch(/ProfitabilityGauge/);
    expect(pageSrc).toMatch(/ebit_actual_total_pct/);
    expect(pageSrc).toMatch(/roi_incl_capex_actual_pct/);
    expect(pageSrc).toMatch(/revenue_by_year/);
  });

  it("exposes accessibility labels and textual status on the gauge", () => {
    expect(gaugeSrc).toMatch(/aria-label/);
    expect(gaugeSrc).toMatch(/zoneLabel/);
    expect(gaugeSrc).toMatch(/nicht verfügbar/);
    expect(gaugeSrc).toMatch(/0–5 % kritisch/);
  });

  it("provides a semantic revenue table as chart alternative", () => {
    expect(chartSrc).toMatch(/<table/);
    expect(chartSrc).toMatch(/sr-only/);
    expect(chartSrc).toMatch(/Für den ausgewählten Business Case liegen noch keine Umsatzwerte vor/);
  });
});
