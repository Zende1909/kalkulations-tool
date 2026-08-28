/** Ergebnisübersicht: FGK additiv genau einmal. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./SpritzgussPage.tsx"), "utf-8");

describe("Spritzguss Ergebnisübersicht FGK", () => {
  it("zeigt additive Aufbauzeilen und FGK einmal vor den Herstellkosten", () => {
    expect(pageSrc).toMatch(/materialkosten_gesamt/);
    expect(pageSrc).toMatch(/FGK-Basis \(Maschine \+ Lohn \+ Setup \+ Veredelung\)/);
    expect(pageSrc).toMatch(/FGK-Betrag \(einmal\)/);
    expect(pageSrc).toMatch(/Herstellkosten \(= Summe inkl\. FGK\)/);
    expect(pageSrc).toMatch(/genau einmal/);
  });

  it("stellt Spritzguss-HK nicht als Summand vor der FGK dar", () => {
    const overviewBlock = pageSrc.slice(
      pageSrc.indexOf("const ERGEBNISUEBERSICHT"),
      pageSrc.indexOf("const FIELD_LABELS"),
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
