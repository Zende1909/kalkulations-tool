/** Material-Formular: Materialgruppe laden und submitten. */
import { describe, expect, it } from "vitest";

import {
  loadMaterialFormValues,
  submitMaterialFormValues,
} from "../../utils/materialFormDecimals";

const BASIS = {
  preis_pro_kg: "2,10",
  dichte: "1,41",
  injection_pressure_kg_cm2: "500",
};

describe("Materialgruppe im Materialformular", () => {
  it("zeigt eine fehlende Gruppe als leere Auswahl", () => {
    const values = loadMaterialFormValues({
      preis_pro_kg: 2.1,
      dichte: 1.41,
      injection_pressure_kg_cm2: 500,
    } as unknown as Record<string, string | number | boolean>);
    expect(values.materialgruppe).toBe("");
  });

  it("übernimmt eine gepflegte Gruppe unverändert", () => {
    const values = loadMaterialFormValues({
      preis_pro_kg: 2.1,
      dichte: 1.41,
      injection_pressure_kg_cm2: 500,
      materialgruppe: "POM",
    } as unknown as Record<string, string | number | boolean>);
    expect(values.materialgruppe).toBe("POM");
    expect(values.preis_pro_kg).toBe("2,1");
  });

  it("sendet eine leere Gruppe als null", () => {
    const payload = submitMaterialFormValues({ ...BASIS, materialgruppe: "" });
    expect(payload.materialgruppe).toBeNull();
  });

  it("sendet die gewählte Gruppe mit", () => {
    const payload = submitMaterialFormValues({ ...BASIS, materialgruppe: "PE-LD" });
    expect(payload.materialgruppe).toBe("PE-LD");
    expect(payload.preis_pro_kg).toBeCloseTo(2.1, 10);
    expect(payload.dichte).toBeCloseTo(1.41, 10);
  });
});
