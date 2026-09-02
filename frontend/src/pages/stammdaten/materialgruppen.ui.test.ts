/** UI: Materialgruppen-Stammdatenseite und Anbindung an Materialien. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./MaterialgruppenPage.tsx"), "utf-8");
const materialPageSrc = readFileSync(resolve(__dirname, "./MaterialienPage.tsx"), "utf-8");
const navSrc = readFileSync(resolve(__dirname, "../../components/layout/navConfig.ts"), "utf-8");
const appSrc = readFileSync(resolve(__dirname, "../../App.tsx"), "utf-8");

describe("Materialgruppen Stammdatenseite", () => {
  it("nutzt StammdatenGrid mit allen thermischen Kennwerten", () => {
    expect(pageSrc).toMatch(/title="Materialgruppen"/);
    expect(pageSrc).toMatch(/endpoint="\/materialgruppen"/);
    expect(pageSrc).toMatch(/schmelzdichte_kg_m3/);
    expect(pageSrc).toMatch(/waermekapazitaet_j_kg_k/);
    expect(pageSrc).toMatch(/waermeleitfaehigkeit_w_m_k/);
    expect(pageSrc).toMatch(/werkzeugtemperatur_c/);
    expect(pageSrc).toMatch(/schmelzetemperatur_c/);
    expect(pageSrc).toMatch(/entformungstemperatur_c/);
  });

  it("ist in Navigation und Routing eingetragen", () => {
    expect(navSrc).toMatch(/\/stammdaten\/materialgruppen/);
    expect(navSrc).toMatch(/Materialgruppen/);
    expect(appSrc).toMatch(/MaterialgruppenPage/);
    expect(appSrc).toMatch(/stammdaten\/materialgruppen/);
  });
});

describe("Materialien-Anbindung", () => {
  it("lädt Materialgruppen aus der API statt hardcoded Liste", () => {
    expect(materialPageSrc).toMatch(/\/materialgruppen\?nur_aktiv=true/);
    expect(materialPageSrc).not.toMatch(/const MATERIALGRUPPEN = \[/);
  });
});
