import { describe, expect, it } from "vitest";

import { emptySpritzgussForm } from "../types/spritzguss";
import {
  buildMaschinenGroessePreviewPayload,
  readKavitaeten,
} from "./maschinenGroessePreview";

describe("maschinenGroessePreview", () => {
  it("liest Kavitäten aus decimalRaw statt aus dem Formular-Fallback", () => {
    expect(readKavitaeten({ kavitaeten: "4" }, 1)).toBe(4);
    expect(readKavitaeten({ kavitaeten: "" }, 1)).toBe(1);
  });

  it("baut Maßeingabe-Payload mit Kavitäten aus decimalRaw", () => {
    const form = {
      ...emptySpritzgussForm(),
      maschinen_groesse_modus: "masse" as const,
      material_id: 5,
      werk_id: 2,
      kavitaeten: 1,
    };
    const payload = buildMaschinenGroessePreviewPayload(form, {
      maschinen_groesse_breite_mm: "100",
      maschinen_groesse_laenge_mm: "200",
      maschinen_groesse_oeffnungen_pct: "10",
      kavitaeten: "4",
    });
    expect(payload?.kavitaeten).toBe(4);
    expect(payload?.maschinen_groesse_breite_mm).toBe(100);
  });

  it("liest Maße auch wenn form-Felder noch null sind (nur decimalRaw befüllt)", () => {
    const form = {
      ...emptySpritzgussForm(),
      maschinen_groesse_modus: "masse" as const,
      material_id: 1,
      // bewusst null – typischer Zustand vor dem Parsen beim Berechnen
      maschinen_groesse_breite_mm: null,
      maschinen_groesse_laenge_mm: null,
      maschinen_groesse_oeffnungen_pct: null,
    };
    const payload = buildMaschinenGroessePreviewPayload(form, {
      maschinen_groesse_breite_mm: "100",
      maschinen_groesse_laenge_mm: "200",
      maschinen_groesse_oeffnungen_pct: "20",
      kavitaeten: "2",
    });
    expect(payload).not.toBeNull();
    expect(payload?.maschinen_groesse_breite_mm).toBe(100);
    expect(payload?.maschinen_groesse_laenge_mm).toBe(200);
    expect(payload?.maschinen_groesse_oeffnungen_pct).toBe(20);
  });

  it("baut Flächen-Payload nur bei vollständigen Eingaben", () => {
    const form = {
      ...emptySpritzgussForm(),
      maschinen_groesse_modus: "flaeche" as const,
      material_id: 1,
      werk_id: 1,
    };
    expect(
      buildMaschinenGroessePreviewPayload(form, {
        maschinen_groesse_proj_flaeche_mm2: "",
        kavitaeten: "1",
      }),
    ).toBeNull();
    expect(
      buildMaschinenGroessePreviewPayload(form, {
        maschinen_groesse_proj_flaeche_mm2: "50000",
        kavitaeten: "1",
      })?.maschinen_groesse_proj_flaeche_mm2,
    ).toBe(50000);
  });
});
