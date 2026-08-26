/** UI: Werkformular – Dezimalparsing und Standortparameter. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { parseDecimalInput } from "../../components/stammdaten/StammdatenFormModal";

const __dirname = dirname(fileURLToPath(import.meta.url));
const werkeSrc = readFileSync(resolve(__dirname, "./WerkePage.tsx"), "utf-8");

describe("Werk-Formular Dezimal / Payload", () => {
  it("parseDecimalInput akzeptiert deutsche und englische Schreibweise", () => {
    expect(parseDecimalInput("0,92")).toBeCloseTo(0.92);
    expect(parseDecimalInput("0.9")).toBeCloseTo(0.9);
    expect(parseDecimalInput("1.234,56")).toBeCloseTo(1234.56);
    expect(parseDecimalInput("")).toBe("");
  });

  it("WerkePage transformiert Submit-Zahlen und pflegt Standortparameter", () => {
    expect(werkeSrc).toMatch(/transformSubmitValues/);
    expect(werkeSrc).toMatch(/fx_to_eur/);
    expect(werkeSrc).toMatch(/Arbeitstage\/Jahr/);
    expect(werkeSrc).toMatch(/OEE \(0–1\)/);
  });
});
