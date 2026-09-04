import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const pageSrc = readFileSync(resolve(__dirname, "./AssemblyFamilyPage.tsx"), "utf-8");
const apiSrc = readFileSync(resolve(__dirname, "../api/assemblyFamilies.ts"), "utf-8");
const typesSrc = readFileSync(resolve(__dirname, "../types/assemblyFamily.ts"), "utf-8");
const appSrc = readFileSync(resolve(__dirname, "../App.tsx"), "utf-8");
const navSrc = readFileSync(resolve(__dirname, "../components/layout/navConfig.ts"), "utf-8");

describe("Assembly family variant mix UI", () => {
  it("wires family route and navigation", () => {
    expect(appSrc).toMatch(/AssemblyFamilyPage/);
    expect(appSrc).toMatch(/baugruppen\/familien/);
    expect(navSrc).toMatch(/Baugruppenfamilien/);
  });

  it("exposes mix share validation messaging and variant fields", () => {
    expect(pageSrc).toMatch(/mix_message/);
    expect(pageSrc).toMatch(/anteil_prozent/);
    expect(pageSrc).toMatch(/jahresmenge/);
    expect(pageSrc).toMatch(/effektive_jahresmenge/);
    expect(pageSrc).toMatch(/100/);
    expect(pageSrc).toMatch(/unvollständig|vollständig|überschritten/);
    expect(pageSrc).toMatch(/Variantenübersicht/);
  });

  it("uses assembly-families API without inventing einkaufsvolumen", () => {
    expect(apiSrc).toMatch(/\/assembly-families/);
    expect(apiSrc).toMatch(/recalculate/);
    expect(apiSrc).toMatch(/variants/);
    expect(apiSrc).not.toMatch(/einkaufsvolumen/i);
    expect(pageSrc).not.toMatch(/einkaufsvolumen/i);
    expect(typesSrc).not.toMatch(/einkaufsvolumen/i);
  });

  it("shows aggregated component quantities and optional lot counts", () => {
    expect(pageSrc).toMatch(/aggregated_components/);
    expect(pageSrc).toMatch(/losgroesse/);
    expect(pageSrc).toMatch(/anzahl_lose/);
    expect(typesSrc).toMatch(/AssemblyFamilyMix/);
  });
});
