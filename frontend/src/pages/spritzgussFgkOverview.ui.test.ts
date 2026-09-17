/** Ergebnisübersicht: FGK additiv genau einmal. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./SpritzgussPage.tsx"), "utf-8");
const labelsSrc = readFileSync(resolve(__dirname, "../i18n/spritzgussLabels.ts"), "utf-8");
const catalogsSrc = readFileSync(resolve(__dirname, "../i18n/catalogs.ts"), "utf-8");

describe("Spritzguss Ergebnisübersicht FGK", () => {
  it("zeigt additive Aufbauzeilen und FGK einmal vor den Herstellkosten", () => {
    expect(pageSrc).toMatch(/materialkosten_gesamt/);
    expect(labelsSrc).toMatch(/spritzguss\.overview\.fgkBase/);
    expect(labelsSrc).toMatch(/spritzguss\.overview\.fgkAmountOnce/);
    expect(labelsSrc).toMatch(/spritzguss\.overview\.manufacturingCost/);
    expect(catalogsSrc).toMatch(/FGK-Basis \(Maschine \+ Lohn \+ Setup \+ Veredelung\)/);
    expect(pageSrc).toMatch(/spritzguss\.resultOverviewHint/);
    expect(catalogsSrc).toMatch(/genau einmal/);
  });

  it("stellt Spritzguss-HK nicht als Summand vor der FGK dar", () => {
    const overviewBlock = labelsSrc.slice(
      labelsSrc.indexOf("export const ERGEBNISUEBERSICHT_DEF"),
      labelsSrc.indexOf("export const DETAIL_BLOCK_ORDER"),
    );
    const sgIdx = overviewBlock.indexOf("spritzguss_herstellkosten");
    const fgkIdx = overviewBlock.indexOf("fertigungsgemeinkosten");
    const hkIdx = overviewBlock.indexOf("gesamte_herstellkosten");
    expect(sgIdx).toBeGreaterThan(-1);
    expect(fgkIdx).toBeGreaterThan(-1);
    expect(hkIdx).toBeGreaterThan(-1);
    // Spritzguss-HK steht nach den Herstellkosten (nur Info „davon …“)
    expect(sgIdx).toBeGreaterThan(hkIdx);
    expect(fgkIdx).toBeLessThan(hkIdx);
  });
});
