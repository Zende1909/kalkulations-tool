import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  loadKaufteilFormValues,
  submitKaufteilFormValues,
} from "../../utils/kaufteilFormDecimals";

const __dirname = dirname(fileURLToPath(import.meta.url));
const kaufteileSrc = readFileSync(resolve(__dirname, "./KaufteilePage.tsx"), "utf-8");
const optionalHierarchySrc = readFileSync(
  resolve(__dirname, "../../components/hierarchy/OptionalHierarchySelector.tsx"),
  "utf-8",
);
const baugruppenSrc = readFileSync(resolve(__dirname, "../BaugruppenPage.tsx"), "utf-8");
const kaufteileApiSrc = readFileSync(resolve(__dirname, "../../api/kaufteile.ts"), "utf-8");

describe("Standardkaufteile UI", () => {
  it("KaufteilePage nutzt optionale Hierarchie im Formular", () => {
    expect(kaufteileSrc).toMatch(/OptionalHierarchySelector/);
    expect(kaufteileSrc).toMatch(/formExtraContent/);
    expect(kaufteileSrc).toMatch(/include_standard/);
  });

  it("OptionalHierarchySelector erklärt Standardkaufteile", () => {
    expect(optionalHierarchySrc).toMatch(/Ohne Projektzuordnung ist dieses Kaufteil ein Standardkaufteil/);
    expect(optionalHierarchySrc).toMatch(/Standardkaufteil \(alle Projekte\)/);
  });

  it("Submit ohne Projekt setzt project_id auf null", () => {
    const payload = submitKaufteilFormValues({
      artikelnummer: "K-1",
      bezeichnung: "Clip",
      preis: "0,10",
      customer_id: "",
      program_id: "",
      project_id: "",
    });
    expect(payload.project_id).toBeNull();
    expect(payload.customer_id).toBeNull();
    expect(payload.program_id).toBeNull();
    expect(payload.preis).toBeCloseTo(0.1);
  });

  it("Submit mit Projekt behält project_id", () => {
    const payload = submitKaufteilFormValues({
      preis: 1,
      customer_id: 1,
      program_id: 2,
      project_id: 10,
    });
    expect(payload.project_id).toBe(10);
  });

  it("bestehende Dezimal-Logik bleibt erhalten", () => {
    expect(loadKaufteilFormValues({ preis: 0.1 }).preis).toBe("0,1");
  });

  it("BaugruppenPage kennzeichnet Standard- und Fremdprojekt-Kaufteile", () => {
    expect(baugruppenSrc).toMatch(/kaufteilListLabel/);
    expect(baugruppenSrc).toMatch(/\(Standard\)/);
    expect(baugruppenSrc).toMatch(/\(anderes Projekt\)/);
    expect(baugruppenSrc).toMatch(/loadedKaufteilIdsRef/);
  });

  it("listKaufteile sendet include_standard bei projectId", () => {
    expect(kaufteileApiSrc).toMatch(/include_standard/);
    expect(kaufteileApiSrc).toMatch(/strict_project/);
  });
});
