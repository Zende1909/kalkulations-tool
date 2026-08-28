/** Baugruppen: Projektfilter und Selbstkosten-Anzeige. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./BaugruppenPage.tsx"), "utf-8");

describe("Baugruppen Projektfilter", () => {
  it("lädt Komponenten nur mit projectId", () => {
    expect(pageSrc).toMatch(/listKalkulationen\(\{ nurAktiv: true, projectId \}/);
    expect(pageSrc).toMatch(/listKaufteile\(\{ nurAktiv: true, projectId \}/);
  });

  it("nutzt Selbstkosten statt Verkaufspreis", () => {
    expect(pageSrc).toMatch(/selbstkosten/);
    expect(pageSrc).toMatch(/Selbstkosten/);
  });

  it("kennzeichnet historische Positionen", () => {
    expect(pageSrc).toMatch(/inaktiv \/ anderes Projekt/);
  });

  it("zeigt Assembly-Kostenüberleitung", () => {
    expect(pageSrc).toMatch(/vorprodukt_gesamt/);
    expect(pageSrc).toMatch(/kostenbasis_nach_assembly/);
    expect(pageSrc).toMatch(/gewinn_betrag/);
  });
});
