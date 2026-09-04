/** UI: Maschinengröße in Einzelteilkalkulation. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./SpritzgussPage.tsx"), "utf-8");
const materialPageSrc = readFileSync(
  resolve(__dirname, "./stammdaten/MaterialienPage.tsx"),
  "utf-8",
);

describe("Maschinengröße UI", () => {
  it("bietet Eingabemodi Maße und Projizierte Fläche", () => {
    expect(pageSrc).toMatch(/Maschinengröße \/ Zuhaltekraft/);
    expect(pageSrc).toMatch(/maschinen_groesse_modus/);
    expect(pageSrc).toMatch(/Projizierte Fläche/);
    expect(pageSrc).toMatch(/maschinenGroesse/);
  });

  it("Material-Stammdaten enthalten Einspritzdruck", () => {
    expect(materialPageSrc).toMatch(/injection_pressure_kg_cm2/);
    expect(materialPageSrc).toMatch(/kg\/cm²/);
  });

  it("nutzt Live-Vorschau und Kavitäten aus Maschine & Lohn", () => {
    expect(pageSrc).toMatch(/berechneMaschinenGroesse/);
    expect(pageSrc).toMatch(/effectiveKavitaeten/);
    expect(pageSrc).not.toMatch(/handleMaschineChange\(String\(maschine\.id\)\)/);
  });

  it("sendet beim Berechnen die geparsten Maschinengröße-Felder aus decimalRaw", () => {
    // Regression: Vorschau las decimalRaw, Berechnen schickte form (oft null) →
    // „Im Modus Maße sind Breite, Länge und Öffnungen erforderlich.“
    expect(pageSrc).toMatch(/const parsedForm = resolveParsedForm\(\)/);
    expect(pageSrc).toMatch(/maschinen_groesse_breite_mm:\s*parsedForm\.maschinen_groesse_breite_mm/);
    expect(pageSrc).toMatch(/maschinen_groesse_laenge_mm:\s*parsedForm\.maschinen_groesse_laenge_mm/);
    expect(pageSrc).toMatch(
      /maschinen_groesse_oeffnungen_pct:\s*parsedForm\.maschinen_groesse_oeffnungen_pct/,
    );
    expect(pageSrc).toMatch(
      /maschinen_groesse_proj_flaeche_mm2:\s*parsedForm\.maschinen_groesse_proj_flaeche_mm2/,
    );
  });
});
