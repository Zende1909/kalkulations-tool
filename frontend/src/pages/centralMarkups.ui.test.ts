import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("Kalkulationsmasken ohne manuelle Zuschlags-%", () => {
  it("Spritzguss zeigt Material-Nominierung und keine manuellen Zuschlags-%", () => {
    const src = readFileSync(
      resolve(__dirname, "../pages/SpritzgussPage.tsx"),
      "utf-8",
    );
    expect(src).not.toMatch(/label=\"MGK %\"/);
    expect(src).not.toMatch(/label=\"FGK %\"/);
    expect(src).not.toMatch(/label=\"VVGK %\"/);
    expect(src).toMatch(/Material-Nominierung/);
    expect(src).toMatch(/selbstnominiert/);
    expect(src).toMatch(/oem_nominiert/);
    expect(src).toMatch(/MGK-Basis \(Material inkl\. Ausschuss\)/);
  });

  it("Veredelung zeigt kein FGK-Eingabefeld", () => {
    const src = readFileSync(
      resolve(__dirname, "../pages/VeredelungPage.tsx"),
      "utf-8",
    );
    expect(src).not.toMatch(/FGK-Zuschlag/);
    expect(src).toMatch(/zentral aus Stammdaten/);
  });

  it("Kaufteile erlauben Nominierung und Projektfilter", () => {
    const src = readFileSync(
      resolve(__dirname, "../pages/stammdaten/KaufteilePage.tsx"),
      "utf-8",
    );
    expect(src).toMatch(/nominierung/);
    expect(src).toMatch(/selbstnominiert/);
    expect(src).toMatch(/oem_nominiert/);
    expect(src).toMatch(/HierarchySelector/);
    expect(src).toMatch(/customer_id/);
  });
});
