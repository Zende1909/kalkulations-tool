/** Navigation: Einzelteilkalkulation + Kaufteile als Hauptmenüpunkt. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  isStammdatenSectionPath,
  navItems,
} from "../components/layout/navConfig";

const __dirname = dirname(fileURLToPath(import.meta.url));
const navConfigSrc = readFileSync(
  resolve(__dirname, "../components/layout/navConfig.ts"),
  "utf-8",
);
const spritzSrc = readFileSync(resolve(__dirname, "./SpritzgussPage.tsx"), "utf-8");
const appSrc = readFileSync(resolve(__dirname, "../App.tsx"), "utf-8");
const kaufteileSrc = readFileSync(
  resolve(__dirname, "./stammdaten/KaufteilePage.tsx"),
  "utf-8",
);
const baugruppenSrc = readFileSync(resolve(__dirname, "./BaugruppenPage.tsx"), "utf-8");

function leafLabelsInOrder(): string[] {
  const labels: string[] = [];
  for (const item of navItems) {
    if ("children" in item) {
      labels.push(item.label);
      for (const child of item.children) {
        labels.push(child.label);
      }
    } else {
      labels.push(item.label);
    }
  }
  return labels;
}

describe("Hauptnavigation Einzelteilkalkulation / Kaufteile", () => {
  it("zeigt Einzelteilkalkulation statt Spritzguss-Kalkulation", () => {
    expect(spritzSrc).toMatch(/Einzelteilkalkulation/);
    expect(spritzSrc).not.toMatch(/Spritzguss-Kalkulation/);
    expect(navConfigSrc).toMatch(/Einzelteilkalkulation/);
    expect(navConfigSrc).not.toMatch(/Spritzguss-Kalkulation/);
    expect(baugruppenSrc).toMatch(/Einzelteilkalkulation hinzufügen/);
    expect(baugruppenSrc).not.toMatch(/Spritzguss-Kalkulation hinzufügen/);
  });

  it("ordnet Kaufteile zwischen Einzelteilkalkulation und Veredelung ein", () => {
    const topLevel = navItems
      .filter((item): item is { to: string; label: string; end?: boolean } => !("children" in item))
      .map((item) => item.label);
    const iEinzel = topLevel.indexOf("Einzelteilkalkulation");
    const iKauf = topLevel.indexOf("Kaufteile");
    const iVered = topLevel.indexOf("Veredelung");
    expect(iEinzel).toBeGreaterThanOrEqual(0);
    expect(iKauf).toBe(iEinzel + 1);
    expect(iVered).toBe(iKauf + 1);
  });

  it("enthält Kaufteile nicht doppelt (nicht unter Stammdaten)", () => {
    const stammdaten = navItems.find(
      (item): item is { label: string; children: { to: string; label: string }[] } =>
        "children" in item && item.label === "Stammdaten",
    );
    expect(stammdaten).toBeDefined();
    expect(stammdaten!.children.some((c) => c.label === "Kaufteile")).toBe(false);
    expect(stammdaten!.children.some((c) => c.to.includes("kaufteile"))).toBe(false);

    const kaufteileLeaves = navItems.filter(
      (item) => !("children" in item) && item.label === "Kaufteile",
    );
    expect(kaufteileLeaves).toHaveLength(1);
    expect(kaufteileLeaves[0]).toMatchObject({ to: "/stammdaten/kaufteile" });
  });

  it("markiert Stammdaten aktiv nur für echte Stammdaten-Unterseiten", () => {
    expect(isStammdatenSectionPath("/stammdaten/maschinen")).toBe(true);
    expect(isStammdatenSectionPath("/stammdaten/materialgruppen")).toBe(true);
    expect(isStammdatenSectionPath("/stammdaten/materialien")).toBe(true);
    expect(isStammdatenSectionPath("/stammdaten/kaufteile")).toBe(false);
    expect(isStammdatenSectionPath("/spritzguss")).toBe(false);
  });

  it("hält Kaufteile-Route und Seite unverändert erreichbar", () => {
    expect(appSrc).toMatch(/path="stammdaten\/kaufteile"/);
    expect(appSrc).toMatch(/KaufteilePage/);
    expect(kaufteileSrc).toMatch(/title="Kaufteile"/);
    expect(kaufteileSrc).toMatch(/endpoint="\/kaufteile"/);
  });

  it("exportiert konsistente Menüreihenfolge", () => {
    const labels = leafLabelsInOrder();
    expect(labels.indexOf("Einzelteilkalkulation")).toBeLessThan(labels.indexOf("Kaufteile"));
    expect(labels.indexOf("Kaufteile")).toBeLessThan(labels.indexOf("Veredelung"));
  });
});
