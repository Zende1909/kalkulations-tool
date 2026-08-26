/** Maschinen-Submit: Dezimalstrings → numerische API-Werte. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  loadMaschineFormValues,
  submitMaschineFormValues,
} from "../../utils/maschineFormDecimals";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./MaschinenPage.tsx"), "utf-8");

describe("Maschine Dezimal-Submit", () => {
  it("wandelt Komma-Werte in Zahlen um", () => {
    const payload = submitMaschineFormValues({
      werk_id: 1,
      maschinen_nr: "IMM-1",
      bezeichnung: "Press",
      schliesskraft_t: "150",
      investment: "347300",
      flaeche_sqm: "44,1",
      stromverbrauch_kwh_h: "50,7",
      druckluftverbrauch_m3_h: "9,9",
      kuehlwasserverbrauch_m3_h: "4,1",
      setup_zeit_min: "30",
      setup_mitarbeiter: "1,5",
      aktiv: true,
      stundensatz: "99",
      stundensatz_source: "100",
      source_currency: "USD",
    });
    expect(payload.flaeche_sqm).toBeCloseTo(44.1);
    expect(payload.stromverbrauch_kwh_h).toBeCloseTo(50.7);
    expect(payload.druckluftverbrauch_m3_h).toBeCloseTo(9.9);
    expect(payload.kuehlwasserverbrauch_m3_h).toBeCloseTo(4.1);
    expect(payload.setup_mitarbeiter).toBeCloseTo(1.5);
    expect(payload.setup_zeit_min).toBe(30);
    expect(payload.schliesskraft_t).toBe(150);
    expect(payload).not.toHaveProperty("stundensatz");
    expect(typeof payload.flaeche_sqm).toBe("number");
  });

  it("akzeptiert Dezimalpunkt und lädt gespeicherte Werte", () => {
    const payload = submitMaschineFormValues({
      werk_id: "2",
      maschinen_nr: "X",
      bezeichnung: "Y",
      schliesskraft_t: 10,
      flaeche_sqm: "44.1",
      stromverbrauch_kwh_h: "50.7",
      aktiv: true,
    });
    expect(payload.flaeche_sqm).toBeCloseTo(44.1);
    expect(payload.werk_id).toBe(2);

    const loaded = loadMaschineFormValues({
      flaeche_sqm: 44.1,
      stromverbrauch_kwh_h: 50.7,
      setup_mitarbeiter: 1.5,
    });
    expect(loaded.flaeche_sqm).toBe("44.1");
    expect(loaded.setup_mitarbeiter).toBe("1.5");
  });

  it("wirft verständlichen Fehler bei ungültiger Dezimalzahl", () => {
    expect(() =>
      submitMaschineFormValues({
        werk_id: 1,
        maschinen_nr: "X",
        bezeichnung: "Y",
        schliesskraft_t: "10",
        flaeche_sqm: "abc",
        aktiv: true,
      }),
    ).toThrow(/Ungültige Zahl/);
  });

  it("MaschinenPage nutzt Submit-/Load-Helfer und keine Werk-Preise", () => {
    expect(pageSrc).toMatch(/submitMaschineFormValues/);
    expect(pageSrc).toMatch(/loadMaschineFormValues/);
    expect(pageSrc).not.toMatch(/name:\s*"strompreis"/);
    expect(pageSrc).not.toMatch(/name:\s*"zinssatz"/);
  });
});
