/** Material-Formular: thermische Kennwerte laden und submitten. */
import { describe, expect, it } from "vitest";

import {
  loadMaterialFormValues,
  MATERIAL_THERMIK_FIELDS,
  submitMaterialFormValues,
} from "../../utils/materialFormDecimals";

describe("Material-Thermikfelder", () => {
  it("zeigt fehlende Werte als leeres Feld", () => {
    const values = loadMaterialFormValues({
      preis_pro_kg: 2.1,
      dichte: 1.41,
      injection_pressure_kg_cm2: 500,
    } as unknown as Record<string, string | number | boolean>);
    for (const key of MATERIAL_THERMIK_FIELDS) {
      expect(values[key]).toBe("");
    }
  });

  it("formatiert gepflegte Werte für die DE-Eingabe", () => {
    const values = loadMaterialFormValues({
      preis_pro_kg: 2.1,
      dichte: 1.41,
      injection_pressure_kg_cm2: 500,
      schmelzdichte_kg_m3: 783.17,
      waermeleitfaehigkeit_w_m_k: 0.27,
    } as unknown as Record<string, string | number | boolean>);
    expect(values.schmelzdichte_kg_m3).toBe("783,17");
    expect(values.waermeleitfaehigkeit_w_m_k).toBe("0,27");
  });

  it("sendet leere Thermikfelder als null", () => {
    const payload = submitMaterialFormValues({
      preis_pro_kg: "2,10",
      dichte: "1,41",
      injection_pressure_kg_cm2: "500",
      materialgruppe: "",
      schmelzdichte_kg_m3: "",
      waermekapazitaet_j_kg_k: "",
      waermeleitfaehigkeit_w_m_k: "",
      werkzeugtemperatur_c: "",
      schmelzetemperatur_c: "",
      entformungstemperatur_c: "",
    });
    expect(payload.materialgruppe).toBeNull();
    for (const key of MATERIAL_THERMIK_FIELDS) {
      expect(payload[key]).toBeNull();
    }
  });

  it("parst DE- und EN-Dezimalwerte der Thermikfelder", () => {
    const payload = submitMaterialFormValues({
      preis_pro_kg: "2,10",
      dichte: "1,41",
      injection_pressure_kg_cm2: "500",
      materialgruppe: "POM",
      schmelzdichte_kg_m3: "783,17",
      waermekapazitaet_j_kg_k: "3000",
      waermeleitfaehigkeit_w_m_k: "0.27",
      werkzeugtemperatur_c: "40",
      schmelzetemperatur_c: "220",
      entformungstemperatur_c: "80",
    });
    expect(payload.materialgruppe).toBe("POM");
    expect(payload.schmelzdichte_kg_m3).toBeCloseTo(783.17, 10);
    expect(payload.waermekapazitaet_j_kg_k).toBe(3000);
    expect(payload.waermeleitfaehigkeit_w_m_k).toBeCloseTo(0.27, 10);
    expect(payload.werkzeugtemperatur_c).toBe(40);
    expect(payload.schmelzetemperatur_c).toBe(220);
    expect(payload.entformungstemperatur_c).toBe(80);
  });
});
