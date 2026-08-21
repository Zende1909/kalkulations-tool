import { describe, expect, it } from "vitest";

import { CENTRAL_MARKUP_TYPEN, ZUSCHLAGSSATZ_TYP_OPTIONS } from "../constants/zuschlagssatzTypen";

describe("zentrale Zuschlagssätze UI", () => {
  it("enthält alle zentralen Typen in den Formular-Optionen", () => {
    const values = ZUSCHLAGSSATZ_TYP_OPTIONS.map((o) => o.value);
    for (const typ of CENTRAL_MARKUP_TYPEN) {
      expect(values).toContain(typ);
    }
  });

  it("Kennzeichnet MGK-Kaufteil-Typen klar", () => {
    expect(
      ZUSCHLAGSSATZ_TYP_OPTIONS.find((o) => o.value === "mgk_kaufteil_selbst")?.label,
    ).toMatch(/selbst/i);
    expect(
      ZUSCHLAGSSATZ_TYP_OPTIONS.find((o) => o.value === "mgk_kaufteil_oem")?.label,
    ).toMatch(/OEM/i);
  });
});
