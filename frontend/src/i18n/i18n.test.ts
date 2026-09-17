import { describe, expect, it } from "vitest";

import { translate } from "../i18n/translate";
import { normalizeLocale } from "../i18n/types";

describe("i18n", () => {
  it("normalizes locale codes", () => {
    expect(normalizeLocale("en-US")).toBe("en");
    expect(normalizeLocale("de-DE")).toBe("de");
    expect(normalizeLocale(null)).toBe("de");
  });

  it("translates shell and business-case keys to business English", () => {
    expect(translate("en", "common.logout")).toBe("Sign out");
    expect(translate("en", "nav.partCalculation")).toBe("Part calculation");
    expect(translate("en", "businessCase.operatingPerformance")).toBe("Operating performance");
    expect(translate("de", "common.logout")).toBe("Abmelden");
  });

  it("translates spritzguss part-calculation keys", () => {
    expect(translate("en", "spritzguss.partImage")).toBe("Part image");
    expect(translate("en", "spritzguss.machineSizeSection")).toBe("Machine size / clamping force");
    expect(translate("en", "spritzguss.shotWeightGross")).toBe(
      "Shot weight / gross (g) — material basis",
    );
    expect(translate("de", "spritzguss.noCalculation")).toBe("Keine Berechnung");
  });

  it("translates master-data keys", () => {
    expect(translate("en", "masterData.pricePerKg")).toBe("Price per kg");
    expect(translate("en", "masterData.oee01")).toBe("OEE (0–1)");
    expect(translate("en", "masterData.nominationMgk")).toBe("Nomination (MGK)");
    expect(translate("de", "masterData.pricePerKg")).toBe("Preis pro kg");
    expect(translate("en", "masterData.createEntity", { entity: "Plant" })).toBe("Create Plant");
  });

  it("translates master-data form chrome", () => {
    expect(translate("de", "masterData.pricePerKg")).toBe("Preis pro kg");
    expect(translate("en", "masterData.pricePerKg")).toBe("Price per kg");
    expect(translate("de", "masterData.createEntity", { entity: "Material" })).toBe(
      "Material anlegen",
    );
    expect(translate("en", "masterData.editEntity", { entity: "Material" })).toBe("Edit Material");
  });

  it("interpolates parameters", () => {
    expect(translate("en", "businessCase.partsAssembliesHint", { parts: 2, assemblies: 1 })).toBe(
      "2 parts · 1 assemblies",
    );
  });
});
