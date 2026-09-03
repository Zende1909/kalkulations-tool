/** UI: Zykluszeit-Schätzung in der Einzelteilkalkulation. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./SpritzgussPage.tsx"), "utf-8");
const materialPageSrc = readFileSync(
  resolve(__dirname, "./stammdaten/MaterialienPage.tsx"),
  "utf-8",
);
const apiSrc = readFileSync(resolve(__dirname, "../api/spritzguss.ts"), "utf-8");

describe("Zykluszeit-Schätzung UI", () => {
  it("kommt mit den zentralen Eingaben aus", () => {
    expect(pageSrc).toMatch(/Zykluszeit-Schätzung/);
    expect(pageSrc).toMatch(/kühlzeitrelevante Wandstärke \(mm\)/);
    expect(pageSrc).toMatch(/Teilegröße/);
    expect(pageSrc).toMatch(/Prozessaufwand/);
    expect(pageSrc).toMatch(/Nebenzeiten gesamt \(s\)/);
  });

  it("verzichtet auf die früheren Detailparameter", () => {
    for (const feld of [
      "zykluszeit_variante",
      "zykluszeit_kuehlfaktor",
      "zykluszeit_komponenten",
      "zykluszeit_nz_werkzeug_schliessen_s",
      "zykluszeit_nz_auswerfen_s",
      "zykluszeit_nz_ausblasen_s",
    ]) {
      expect(pageSrc).not.toContain(feld);
      expect(apiSrc).not.toContain(feld);
    }
  });

  it("bietet die Größenklassen und Prozessaufwand an", () => {
    expect(pageSrc).toMatch(/ZYKLUSZEIT_GROESSENKLASSEN\.map/);
    expect(pageSrc).toMatch(/zykluszeit_groessenklasse/);
    expect(pageSrc).toMatch(/zykluszeit_prozessaufwand/);
    expect(pageSrc).toMatch(
      /nebenzeitenRichtwert\(\s*form\.zykluszeit_groessenklasse,\s*zuhaltekraftT,\s*form\.zykluszeit_prozessaufwand/,
    );
  });

  it("leitet die Teilegröße auf Wunsch aus der Zuhaltekraft ab", () => {
    expect(pageSrc).toMatch(/Automatisch aus Zuhaltekraft/);
    expect(pageSrc).toMatch(/ZYKLUSZEIT_GROESSENKLASSE_AUTO/);
    expect(pageSrc).toMatch(/maschinenGroesse\?\.zuhaltekraft_erforderlich_t/);
    expect(pageSrc).toMatch(/teilegroesseAusZuhaltekraft/);
    expect(pageSrc).toMatch(
      /buildZykluszeitPreviewPayload\(form,\s*decimalRaw,\s*zuhaltekraftT\)/,
    );
  });

  it("erklärt, dass Kavitäten nur über die Nebenzeiten wirken", () => {
    expect(pageSrc).toMatch(/Kavitätenzahl verlängert die Kühlzeit nicht/);
    expect(pageSrc).toMatch(/bis 100 t klein, bis 300 t mittel, darüber groß/);
  });

  it("rechnet live mit Debounce wie die Maschinengrößen-Vorschau", () => {
    expect(pageSrc).toMatch(/berechneZykluszeit/);
    expect(pageSrc).toMatch(/buildZykluszeitPreviewPayload/);
    expect(pageSrc).toMatch(/setTimeout\([\s\S]{0,400}berechneZykluszeit/);
    expect(apiSrc).toMatch(/\/spritzguss\/zykluszeit\/berechnen/);
  });

  it("zeigt Kühlzeit, Nebenzeiten und die genutzten Materialkennwerte", () => {
    expect(pageSrc).toMatch(/zykluszeitVorschlag\.kuehlzeit_s/);
    expect(pageSrc).toMatch(/zykluszeitVorschlag\.nebenzeiten_gesamt_s/);
    expect(pageSrc).toMatch(/zykluszeitVorschlag\.materialgruppe/);
    expect(pageSrc).toMatch(/theoretische Kühlzeit/);
    expect(pageSrc).toMatch(/zykluszeitVorschlag\.optimale_kuehlzeit_s/);
  });

  it("schreibt den Vorschlag erst nach Klick auf Übernehmen ins Zykluszeitfeld", () => {
    expect(pageSrc).toMatch(/uebernehmeZykluszeit/);
    expect(pageSrc).toMatch(/>\s*Übernehmen\s*<\/button>/);
    expect(pageSrc).toMatch(/zykluszeit_s: wert,\s*zykluszeit_quelle: "vorschlag"/);
    // Kein automatisches Überschreiben aus dem Vorschau-Effekt heraus.
    expect(pageSrc).not.toMatch(
      /setZykluszeitVorschlag\(result\);\s*setField\("zykluszeit_s"/,
    );
  });

  it("markiert manuelle Eingaben als Quelle manuell", () => {
    expect(pageSrc).toMatch(
      /fieldKey === "zykluszeit_s"[\s\S]{0,160}zykluszeit_quelle: "manuell"/,
    );
    expect(pageSrc).toMatch(/aus Vorschlag übernommen/);
    expect(pageSrc).toMatch(/manuell erfasst/);
  });

  it("zeigt einen Hinweis, wenn keine Schätzung möglich ist", () => {
    expect(pageSrc).toMatch(/zykluszeitVorschlag\?\.hinweis/);
    expect(pageSrc).toMatch(/berechenbar/);
  });

  it("stellt gespeicherte Werte beim Neuladen wieder her", () => {
    expect(pageSrc).toMatch(/item\.zykluszeit_wandstaerke_mm/);
    expect(pageSrc).toMatch(/item\.zykluszeit_groessenklasse/);
    expect(pageSrc).toMatch(/item\.zykluszeit_prozessaufwand/);
    expect(pageSrc).toMatch(/item\.zykluszeit_nebenzeiten_gesamt_s/);
    expect(pageSrc).toMatch(/item\.zykluszeit_quelle/);
  });

  it("sendet die Zykluszeitfelder an Berechnen und Speichern", () => {
    expect(pageSrc).toMatch(/zykluszeit_quelle: form\.zykluszeit_quelle/);
    expect(pageSrc).toMatch(/zykluszeit_wandstaerke_mm: form\.zykluszeit_wandstaerke_mm/);
    expect(pageSrc).toMatch(/zykluszeit_groessenklasse: form\.zykluszeit_groessenklasse/);
    expect(pageSrc).toMatch(/zykluszeit_prozessaufwand: form\.zykluszeit_prozessaufwand/);
    expect(apiSrc).toMatch(/"zykluszeit_wandstaerke_mm"/);
    expect(apiSrc).toMatch(/"zykluszeit_prozessaufwand"/);
    expect(apiSrc).toMatch(/"zykluszeit_nebenzeiten_gesamt_s"/);
  });
});

describe("Material-Stammdaten", () => {
  it("fragt die Materialgruppe aus den Stammdaten ab", () => {
    expect(materialPageSrc).toMatch(/materialgruppe/);
    expect(materialPageSrc).toMatch(/\/materialgruppen\?nur_aktiv=true/);
  });

  it("verlangt keine thermischen Einzelwerte mehr", () => {
    for (const feld of [
      "schmelzdichte_kg_m3",
      "waermekapazitaet_j_kg_k",
      "waermeleitfaehigkeit_w_m_k",
      "werkzeugtemperatur_c",
      "schmelzetemperatur_c",
      "entformungstemperatur_c",
    ]) {
      expect(materialPageSrc).not.toContain(feld);
    }
  });
});
