/** Navigation und UI: Maschinenauslastung. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { navItems } from "../components/layout/navConfig";

const __dirname = dirname(fileURLToPath(import.meta.url));
const navConfigSrc = readFileSync(
  resolve(__dirname, "../components/layout/navConfig.ts"),
  "utf-8",
);
const appSrc = readFileSync(resolve(__dirname, "../App.tsx"), "utf-8");
const pageSrc = readFileSync(resolve(__dirname, "./MaschinenauslastungPage.tsx"), "utf-8");
const apiSrc = readFileSync(resolve(__dirname, "../api/maschinen.ts"), "utf-8");

describe("Maschinenauslastung Navigation", () => {
  it("enthält Menüpunkt und Route", () => {
    expect(navConfigSrc).toMatch(/Maschinenauslastung/);
    expect(appSrc).toMatch(/maschinenauslastung/);
    expect(appSrc).toMatch(/MaschinenauslastungPage/);
    const labels = navItems
      .filter((item): item is { to: string; label: string } => !("children" in item))
      .map((item) => item.label);
    expect(labels).toContain("Maschinenauslastung");
  });

  it("Seite nutzt API und deutsche Prozentformatierung", () => {
    expect(pageSrc).toMatch(/getMaschinenAuslastung/);
    expect(pageSrc).toMatch(/formatPercentOrDash/);
    expect(pageSrc).toMatch(/Keine Projekte ausgewählt/);
    expect(apiSrc).toMatch(/\/maschinen\/auslastung/);
    expect(apiSrc).toMatch(/project_ids/);
  });

  it("Filter-Kaskade Werk → Kunde → Programm → Projekte", () => {
    expect(pageSrc).toMatch(/setPlantId/);
    expect(pageSrc).toMatch(/setCustomerId\(null\)/);
    expect(pageSrc).toMatch(/setProgramId\(null\)/);
    expect(pageSrc).toMatch(/selectedProjectIds/);
    expect(pageSrc).toMatch(/type="checkbox"/);
  });
});
