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
});
