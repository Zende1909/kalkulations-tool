/** Werk-%-Umwandlung und Dezimalparsing. */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  fractionToUiPercent,
  parseDecimalInput,
  uiPercentToFraction,
  formatPercentPoints,
} from "../../utils/decimalInput";

const __dirname = dirname(fileURLToPath(import.meta.url));
const werkeSrc = readFileSync(resolve(__dirname, "./WerkePage.tsx"), "utf-8");
const maschinenSrc = readFileSync(resolve(__dirname, "./MaschinenPage.tsx"), "utf-8");
const utilSrc = readFileSync(
  resolve(__dirname, "../../utils/decimalInput.ts"),
  "utf-8",
);
const spritzSrc = readFileSync(
  resolve(__dirname, "../SpritzgussPage.tsx"),
  "utf-8",
);
const veredSrc = readFileSync(resolve(__dirname, "../VeredelungPage.tsx"), "utf-8");

describe("Werk rate UI percent ↔ fraction", () => {
  it("UI 8 % → intern 0,08; Laden 0,08 → 8", () => {
    expect(uiPercentToFraction(8)).toBeCloseTo(0.08);
    expect(uiPercentToFraction(0.45)).toBeCloseTo(0.0045);
    expect(uiPercentToFraction(2)).toBeCloseTo(0.02);
    expect(fractionToUiPercent(0.08)).toBeCloseTo(8);
    expect(fractionToUiPercent(0.0045)).toBeCloseTo(0.45);
    expect(fractionToUiPercent(0.02)).toBeCloseTo(2);
  });

  it("Altdaten > 1 werden nicht ×100 skaliert", () => {
    expect(fractionToUiPercent(8)).toBe(8);
  });

  it("OEE bleibt Anteil (keine /100-Hilfsfunktion)", () => {
    expect(werkeSrc).toMatch(/OEE \(0–1\)/);
    expect(utilSrc).toMatch(/zinssatz/);
    expect(utilSrc).not.toMatch(/oee/);
    expect(werkeSrc).toMatch(/WERK_RATE_FRACTION_FIELDS/);
  });

  it("Werkfelder haben %-Labels und Hinweis", () => {
    expect(werkeSrc).toMatch(/Zinssatz \(%\)/);
    expect(werkeSrc).toMatch(/Versicherungssatz \(%\)/);
    expect(werkeSrc).toMatch(/Instandhaltungssatz \(%\)/);
    expect(werkeSrc).toMatch(/Eingabe als Prozentwert/);
    expect(werkeSrc).toMatch(/step: "0\.0001"/);
  });

  it("Maschinenmaske enthält keine Werk-Kostensätze", () => {
    expect(maschinenSrc).not.toMatch(/name:\s*"zinssatz"/);
    expect(maschinenSrc).not.toMatch(/name:\s*"versicherungssatz"/);
  });
});

describe("Dezimalparsing und Prozentanzeige", () => {
  it("akzeptiert Komma und Punkt", () => {
    expect(parseDecimalInput("0,45")).toBeCloseTo(0.45);
    expect(parseDecimalInput("0.45")).toBeCloseTo(0.45);
    expect(parseDecimalInput("2,5000")).toBeCloseTo(2.5);
  });

  it("formatPercentPoints ohne Euro-Suffix", () => {
    expect(formatPercentPoints(2.5)).toBe("2,5 %");
    expect(formatPercentPoints(22)).toMatch(/%/);
    expect(formatPercentPoints(22)).not.toMatch(/€/);
  });

  it("Spritzguss/Veredelung nutzen zentrale Dezimal-Helfer", () => {
    expect(spritzSrc).toMatch(/parseSpritzgussDecimalFields|FormDecimalInput/);
    expect(spritzSrc).toMatch(/formatPercentPoints|formatDetailValue/);
    expect(veredSrc).toMatch(/parseVeredelungDecimalFields|FormDecimalInput/);
  });
});
