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

describe("Kaufteil Dezimaleingabe", () => {
  it("parst 0,10 und 0.10 beim Submit", () => {
    expect(submitKaufteilFormValues({ preis: "0,10" }).preis).toBeCloseTo(0.1);
    expect(submitKaufteilFormValues({ preis: "0.10" }).preis).toBeCloseTo(0.1);
  });

  it("formatiert geladene Werte für DE-Eingabe", () => {
    expect(loadKaufteilFormValues({ preis: 0.1 }).preis).toBe("0,1");
  });

  it("KaufteilePage nutzt transformLoad/Submit", () => {
    expect(kaufteileSrc).toMatch(/loadKaufteilFormValues/);
    expect(kaufteileSrc).toMatch(/submitKaufteilFormValues/);
  });
});
