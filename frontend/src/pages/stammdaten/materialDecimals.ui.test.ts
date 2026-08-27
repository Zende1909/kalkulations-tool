/** Material-Submit: Preis/Dichte mit Dezimalkomma. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  loadMaterialFormValues,
  submitMaterialFormValues,
} from "../../utils/materialFormDecimals";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./MaterialienPage.tsx"), "utf-8");

describe("Material Dezimal-Submit", () => {
  it("wandelt 2,10 und 2.10 in 2.10 um", () => {
    const a = submitMaterialFormValues({
      material_nr: "M1",
      bezeichnung: "PA6",
      preis_pro_kg: "2,10",
      dichte: "1,04",
      waehrung: "EUR",
      aktiv: true,
    });
    expect(a.preis_pro_kg).toBeCloseTo(2.1);
    expect(a.dichte).toBeCloseTo(1.04);
    expect(typeof a.preis_pro_kg).toBe("number");

    const b = submitMaterialFormValues({
      material_nr: "M2",
      bezeichnung: "PA6",
      preis_pro_kg: "2.10",
      dichte: "1.0400",
      waehrung: "EUR",
      aktiv: true,
    });
    expect(b.preis_pro_kg).toBeCloseTo(2.1);
    expect(b.dichte).toBeCloseTo(1.04);
  });

  it("erlaubt mehrere Nachkommastellen und lädt gespeicherte Werte", () => {
    const payload = submitMaterialFormValues({
      material_nr: "M3",
      bezeichnung: "X",
      preis_pro_kg: "2,1234",
      dichte: "0,955",
      waehrung: "EUR",
      aktiv: true,
    });
    expect(payload.preis_pro_kg).toBeCloseTo(2.1234);
    expect(payload.dichte).toBeCloseTo(0.955);

    const loaded = loadMaterialFormValues({
      preis_pro_kg: 2.1,
      dichte: 1.04,
    });
    expect(loaded.preis_pro_kg).toBe("2.1");
    expect(loaded.dichte).toBe("1.04");
  });

  it("wirft verständlichen Fehler bei ungültiger Eingabe", () => {
    expect(() =>
      submitMaterialFormValues({
        material_nr: "M4",
        bezeichnung: "X",
        preis_pro_kg: "abc",
        dichte: "1",
        waehrung: "EUR",
        aktiv: true,
      }),
    ).toThrow(/Ungültige Zahl/);
  });

  it("MaterialienPage nutzt Load-/Submit-Helfer", () => {
    expect(pageSrc).toMatch(/submitMaterialFormValues/);
    expect(pageSrc).toMatch(/loadMaterialFormValues/);
    expect(pageSrc).toMatch(/Preis pro kg/);
  });
});
