/** Ergebnisübersicht Einzelteilkalkulation: Hierarchie und Kapazitäts-Trennung. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./SpritzgussPage.tsx"), "utf-8");

function overviewBlock(): string {
  return pageSrc.slice(
    pageSrc.indexOf("const ERGEBNISUEBERSICHT"),
    pageSrc.indexOf("const FIELD_LABELS"),
  );
}

function overviewKeys(): string[] {
  return [...overviewBlock().matchAll(/key:\s*"([^"]+)"/g)].map((m) => m[1]);
}

describe("Spritzguss Ergebnisdarstellung", () => {
  it("zeigt Kapazitätswerte nicht in der Ergebnisübersicht", () => {
    const block = overviewBlock();
    expect(block).not.toMatch(/key:\s*"bruttokapazitaet_exakt"/);
    expect(block).not.toMatch(/key:\s*"bruttokapazitaet"/);
    expect(block).not.toMatch(/key:\s*"nettokapazitaet"/);
  });

  it("behält Kapazitätswerte im Detailbereich (FIELD_LABELS / Fertigung)", () => {
    expect(pageSrc).toMatch(/bruttokapazitaet_exakt:\s*"Bruttokapazität exakt/);
    expect(pageSrc).toMatch(/bruttokapazitaet:\s*"Bruttokapazität kalkulatorisch ROUND/);
    expect(pageSrc).toMatch(/nettokapazitaet:\s*"Nettokapazität nach Ausschuss/);
    expect(pageSrc).toMatch(/"fertigung"/);
    expect(pageSrc).toMatch(/Detailbereiche/);
  });

  it("lässt Herstellkosten sichtbar, aber ohne Hervorhebung", () => {
    const block = overviewBlock();
    const hkEntry = block.match(/\{\s*key:\s*"gesamte_herstellkosten"[\s\S]*?\},/);
    expect(hkEntry).toBeTruthy();
    expect(hkEntry![0]).not.toMatch(/emphasis:/);
  });

  it("hebt Selbstkosten als zentrale Ergebniszeile hervor", () => {
    const block = overviewBlock();
    expect(block).toMatch(/key:\s*"selbstkosten"[\s\S]*?emphasis:\s*"primary"/);
    expect(pageSrc).toMatch(/ergebnisUebersichtRowClass/);
    expect(pageSrc).toMatch(/text-lg font-bold/);
  });

  it("behält Endpreis sichtbar mit schwächerer Hervorhebung als Selbstkosten", () => {
    const block = overviewBlock();
    expect(block).toMatch(/key:\s*"endpreis_je_stueck"[\s\S]*?emphasis:\s*"secondary"/);
    const primaryIdx = pageSrc.indexOf('emphasis === "primary"');
    const secondaryIdx = pageSrc.indexOf('emphasis === "secondary"');
    expect(primaryIdx).toBeGreaterThan(-1);
    expect(secondaryIdx).toBeGreaterThan(-1);
    expect(pageSrc.indexOf("text-lg font-bold")).toBeLessThan(
      pageSrc.indexOf("text-base font-semibold"),
    );
  });

  it("behält die fachliche Reihenfolge der Ergebniszeilen", () => {
    expect(overviewKeys()).toEqual([
      "materialkosten_gesamt",
      "maschinenkosten",
      "fertigungslohn",
      "setup_kosten_je_teil",
      "veredelung_gesamt",
      "fgk_basis",
      "fertigungsgemeinkosten",
      "gesamte_herstellkosten",
      "vvgk",
      "selbstkosten",
      "gewinn",
      "nettoverkaufspreis_gesamt",
      "skonto",
      "endpreis_je_stueck",
      "spritzguss_herstellkosten",
    ]);
  });

  it("ändert keine Berechnungslogik (nur Darstellung)", () => {
    expect(pageSrc).toMatch(/const ergebnisUebersicht = useMemo/);
    expect(pageSrc).not.toMatch(/berechne_spritzguss/);
    expect(pageSrc).not.toMatch(/materialkosten_gesamt \*/);
  });
});
