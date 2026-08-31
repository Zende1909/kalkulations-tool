/** Navigation und UI: Maschinenauslastung Jahresauslastung. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { UTILIZATION_YEARS } from "../types/maschineAuslastung";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./MaschinenauslastungPage.tsx"), "utf-8");
const typesSrc = readFileSync(resolve(__dirname, "../types/maschineAuslastung.ts"), "utf-8");

describe("Maschinenauslastung Jahres-UI", () => {
  it("definiert Jahre 2026 bis 2040", () => {
    expect(UTILIZATION_YEARS[0]).toBe(2026);
    expect(UTILIZATION_YEARS[UTILIZATION_YEARS.length - 1]).toBe(2040);
    expect(UTILIZATION_YEARS).toHaveLength(15);
  });

  it("zeigt Jahrestabelle mit Lauf- und Rüstzeit", () => {
    expect(pageSrc).toMatch(/Laufzeit/);
    expect(pageSrc).toMatch(/Rüstzeit/);
    expect(pageSrc).toMatch(/Brutto h/);
    expect(pageSrc).toMatch(/formatPercentOrDash/);
    expect(pageSrc).toMatch(/selectedYear/);
  });

  it("Typen enthalten API-Jahresbreakdown-Felder", () => {
    expect(typesSrc).toMatch(/run_hours/);
    expect(typesSrc).toMatch(/setup_hours/);
    expect(typesSrc).toMatch(/gross_hours/);
    expect(typesSrc).toMatch(/yearly_rows/);
  });

  it("Kennzeichnet OEE-Transparenz", () => {
    expect(pageSrc).toMatch(/oee_in_available_hours/);
    expect(pageSrc).toMatch(/formatOee/);
  });
});
