import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  formatDecimalForInputDe,
  isIncompleteDecimalInput,
  parsePercentPointsInput,
  PercentPointsParseError,
} from "../utils/decimalInput";

const __dirname = dirname(fileURLToPath(import.meta.url));
const spritzSrc = readFileSync(resolve(__dirname, "./SpritzgussPage.tsx"), "utf-8");

describe("Ausschussquote Dezimalkomma", () => {
  it("parst 1,5 und 1.5 als Prozentpunkte 1.5", () => {
    expect(parsePercentPointsInput("1,5")).toBeCloseTo(1.5);
    expect(parsePercentPointsInput("1.5")).toBeCloseTo(1.5);
  });

  it("behält Zwischenstände als unvollständig", () => {
    expect(isIncompleteDecimalInput("1,")).toBe(true);
    expect(isIncompleteDecimalInput("1.")).toBe(true);
    expect(() => parsePercentPointsInput("1,")).toThrow(PercentPointsParseError);
  });

  it("parst mehrere Nachkommastellen", () => {
    expect(parsePercentPointsInput("2,375")).toBeCloseTo(2.375);
    expect(parsePercentPointsInput("2.375")).toBeCloseTo(2.375);
  });

  it("formatiert geladene Werte für DE-Eingabe", () => {
    expect(formatDecimalForInputDe(1.5)).toBe("1,5");
    expect(formatDecimalForInputDe(0)).toBe("0");
  });

  it("akzeptiert 0 % und leere Eingabe", () => {
    expect(parsePercentPointsInput("0")).toBe(0);
    expect(parsePercentPointsInput("0,0")).toBe(0);
    expect(parsePercentPointsInput("")).toBe(0);
  });

  it("lehnt ungültige und out-of-range Werte ab", () => {
    expect(() => parsePercentPointsInput("abc")).toThrow(PercentPointsParseError);
    expect(() => parsePercentPointsInput("-1")).toThrow(PercentPointsParseError);
    expect(() => parsePercentPointsInput("100")).toThrow(PercentPointsParseError);
  });
});

describe("SpritzgussPage Ausschussquote Rohstring", () => {
  it("nutzt decimalRaw mit Submit-Parse", () => {
    expect(spritzSrc).toMatch(/decimalRaw/);
    expect(spritzSrc).toMatch(/parseSpritzgussDecimalFields/);
    expect(spritzSrc).toMatch(/fieldKey="ausschussquote_pct"/);
  });
});
