import { describe, expect, it } from "vitest";

import {
  DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE,
  berechneAutomatischeLosgroesse,
  inferLegacyLosgroesseModus,
  werkProduktionsintervall,
} from "./losgroesseBerechnung";

describe("losgroesseBerechnung", () => {
  it("verwendet 30 Arbeitstage als Standard", () => {
    expect(DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE).toBe(30);
    expect(werkProduktionsintervall(null)).toBe(30);
    expect(werkProduktionsintervall({ produktionsintervall_arbeitstage: null })).toBe(30);
  });

  it("berechnet 20.000 × 30 / 254 = 2.363", () => {
    expect(berechneAutomatischeLosgroesse(20_000, 30, 254)).toBe(2363);
  });

  it("berechnet 41.875 × 30 / 254 = 4.946", () => {
    expect(berechneAutomatischeLosgroesse(41_875, 30, 254)).toBe(4946);
  });

  it("liefert null bei fehlendem Jahresbedarf", () => {
    expect(berechneAutomatischeLosgroesse(0, 30, 254)).toBeNull();
  });

  it("erkennt Legacy-Manuellmodus", () => {
    expect(inferLegacyLosgroesseModus(null, 4808)).toBe("manuell");
    expect(inferLegacyLosgroesseModus(null, null)).toBe("automatisch");
    expect(inferLegacyLosgroesseModus("automatisch", 4808)).toBe("automatisch");
  });
});
