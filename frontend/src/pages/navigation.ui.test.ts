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

function leafLabelKeysInOrder(): string[] {
  const keys: string[] = [];
  for (const item of navItems) {
    if ("children" in item) {
      keys.push(item.labelKey);
      for (const child of item.children) {
        keys.push(child.labelKey);
      }
    } else {
      keys.push(item.labelKey);
    }
  }
  return keys;
}

describe("Hauptnavigation Einzelteilkalkulation / Kaufteile", () => {
  it("zeigt Einzelteilkalkulation statt Spritzguss-Kalkulation", () => {
    expect(spritzSrc).toMatch(/spritzguss\.title|nav\.partCalculation/);
    expect(spritzSrc).not.toMatch(/Spritzguss-Kalkulation/);
    expect(navConfigSrc).toMatch(/nav\.partCalculation/);
    expect(navConfigSrc).not.toMatch(/Spritzguss-Kalkulation/);
    expect(baugruppenSrc).toMatch(/assemblies\.addMoldedPart/);
    expect(baugruppenSrc).not.toMatch(/Spritzguss-Kalkulation hinzufügen/);
  });

  it("ordnet Kaufteile zwischen Einzelteilkalkulation und Veredelung ein", () => {
    const topLevel = navItems
      .filter(
        (item): item is { to: string; labelKey: string; end?: boolean } => !("children" in item),
      )
      .map((item) => item.labelKey);
    const iEinzel = topLevel.indexOf("nav.partCalculation");
    const iKauf = topLevel.indexOf("nav.purchasedParts");
    const iVered = topLevel.indexOf("nav.finishing");
    expect(iEinzel).toBeGreaterThanOrEqual(0);
    expect(iKauf).toBe(iEinzel + 1);
    expect(iVered).toBe(iKauf + 1);
  });

  it("enthält Kaufteile nicht doppelt (nicht unter Stammdaten)", () => {
    const stammdaten = navItems.find(
      (item): item is { labelKey: string; children: { to: string; labelKey: string }[] } =>
        "children" in item && item.labelKey === "nav.masterData",
    );
    expect(stammdaten).toBeDefined();
    expect(stammdaten!.children.some((c) => c.labelKey === "nav.purchasedParts")).toBe(false);
    expect(stammdaten!.children.some((c) => c.to.includes("kaufteile"))).toBe(false);

    const kaufteileLeaves = navItems.filter(
      (item) => !("children" in item) && item.labelKey === "nav.purchasedParts",
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
    expect(kaufteileSrc).toMatch(/nav\.purchasedParts/);
    expect(kaufteileSrc).toMatch(/endpoint="\/kaufteile"/);
  });

  it("exportiert konsistente Menüreihenfolge", () => {
    const keys = leafLabelKeysInOrder();
    expect(keys.indexOf("nav.partCalculation")).toBeLessThan(keys.indexOf("nav.purchasedParts"));
    expect(keys.indexOf("nav.purchasedParts")).toBeLessThan(keys.indexOf("nav.finishing"));
  });
});
