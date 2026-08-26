/** Absolute Werk-Dezimalpreise: Komma/Punkt, keine %-Umwandlung. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  isIncompleteDecimalInput,
  parseDecimalInput,
} from "../../utils/decimalInput";
import {
  loadWerkFormValues,
  submitWerkFormValues,
} from "../../utils/werkFormDecimals";

const __dirname = dirname(fileURLToPath(import.meta.url));
const modalSrc = readFileSync(
  resolve(__dirname, "../../components/stammdaten/StammdatenFormModal.tsx"),
  "utf-8",
);
const werkeSrc = readFileSync(resolve(__dirname, "./WerkePage.tsx"), "utf-8");

describe("Werk absolute Dezimalpreise", () => {
  it("parst Strompreis 0,06 und 0.06", () => {
    expect(parseDecimalInput("0,06")).toBeCloseTo(0.06);
    expect(parseDecimalInput("0.06")).toBeCloseTo(0.06);
  });

  it("parst Kühlwasser 0,03 und Space/Druckluft-Dezimalwerte", () => {
    expect(parseDecimalInput("0,03")).toBeCloseTo(0.03);
    expect(parseDecimalInput("0.06")).toBeCloseTo(0.06);
    expect(parseDecimalInput("1,25")).toBeCloseTo(1.25);
    expect(parseDecimalInput("30,5")).toBeCloseTo(30.5);
  });

  it("erkennt unvollständige Eingaben wie 0, ohne sie zu speichern", () => {
    expect(isIncompleteDecimalInput("0,")).toBe(true);
    expect(isIncompleteDecimalInput("0.")).toBe(true);
    expect(isIncompleteDecimalInput("0,06")).toBe(false);
  });

  it("Submit speichert absolute Preise ohne /100", () => {
    const payload = submitWerkFormValues({
      land_id: 1,
      code: "T",
      name: "T",
      currency: "USD",
      fx_to_eur: "0,92",
      oee: "0,9",
      zinssatz: "8",
      versicherungssatz: "0,45",
      instandhaltungssatz: "2",
      strompreis: "0,06",
      druckluftpreis: "0.06",
      kuehlwasserpreis: "0,03",
      space_cost_satz_pro_sqm_jahr: "30,5",
      aktiv: true,
    });
    expect(payload.strompreis).toBeCloseTo(0.06);
    expect(payload.druckluftpreis).toBeCloseTo(0.06);
    expect(payload.kuehlwasserpreis).toBeCloseTo(0.03);
    expect(payload.space_cost_satz_pro_sqm_jahr).toBeCloseTo(30.5);
    // Prozentfelder weiterhin UI → Anteil
    expect(payload.zinssatz).toBeCloseTo(0.08);
    expect(payload.versicherungssatz).toBeCloseTo(0.0045);
    expect(payload.instandhaltungssatz).toBeCloseTo(0.02);
    // OEE unverändert Anteil
    expect(payload.oee).toBeCloseTo(0.9);
  });

  it("Laden zeigt gespeicherte Dezimalpreise und UI-% korrekt", () => {
    const loaded = loadWerkFormValues({
      land_id: 1,
      strompreis: 0.06,
      druckluftpreis: 0.06,
      kuehlwasserpreis: 0.03,
      space_cost_satz_pro_sqm_jahr: 30.5,
      zinssatz: 0.08,
      oee: 0.9,
    });
    expect(loaded.strompreis).toBe("0.06");
    expect(loaded.druckluftpreis).toBe("0.06");
    expect(loaded.kuehlwasserpreis).toBe("0.03");
    expect(loaded.space_cost_satz_pro_sqm_jahr).toBe("30.5");
    expect(loaded.zinssatz).toBe("8");
    expect(loaded.oee).toBe("0.9");
  });

  it("Modal speichert Zahleneingaben als Rohstring (kein Live-Number)", () => {
    expect(modalSrc).toMatch(/Kein Live-Parse zu number/);
    expect(modalSrc).toMatch(/inputMode=\{field\.type === "number" \? "decimal"/);
  });

  it("WerkePage zeigt Einheiten an den Preisfeldern", () => {
    expect(werkeSrc).toMatch(/Strompreis \(€\/kWh\)/);
    expect(werkeSrc).toMatch(/Druckluftpreis \(€\/m³\)/);
    expect(werkeSrc).toMatch(/Kühlwasserpreis \(€\/m³\)/);
    expect(werkeSrc).toMatch(/Space-Satz \(€\/m²\/a\)/);
  });
});
