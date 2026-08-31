/** UI: Zykluszeitvorschlag (IKET) in der Einzelteilkalkulation. */
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

describe("Zykluszeitvorschlag UI", () => {
  it("zeigt den Bereich mit Wandstärke, Variante und Kühlfaktor", () => {
    expect(pageSrc).toMatch(/Zykluszeitvorschlag \(IKET\)/);
    expect(pageSrc).toMatch(/zykluszeit_wandstaerke_mm/);
    expect(pageSrc).toMatch(/Äquivalente Wandstärke \(mm\)/);
    expect(pageSrc).toMatch(/zykluszeit_variante/);
    expect(pageSrc).toMatch(/Zuschlagfaktor Werkzeugkühlung/);
  });

  it("bietet alle neun Nebenzeiten aus dem IKET-Blatt", () => {
    for (const feld of [
      "zykluszeit_nz_werkzeug_schliessen_s",
      "zykluszeit_nz_duese_anlegen_s",
      "zykluszeit_nz_einspritzen_s",
      "zykluszeit_nz_werkzeug_oeffnen_s",
      "zykluszeit_nz_auswerfen_s",
      "zykluszeit_nz_kernzug_s",
      "zykluszeit_nz_ausschrauben_s",
      "zykluszeit_nz_einlegen_s",
      "zykluszeit_nz_ausblasen_s",
    ]) {
      expect(pageSrc).toContain(feld);
    }
    expect(pageSrc).toMatch(/ZYKLUSZEIT_NEBENZEITEN\.map/);
  });

  it("rechnet live mit Debounce wie die Maschinengrößen-Vorschau", () => {
    expect(pageSrc).toMatch(/berechneZykluszeit/);
    expect(pageSrc).toMatch(/buildZykluszeitPreviewPayload/);
    expect(pageSrc).toMatch(/setTimeout\([\s\S]{0,400}berechneZykluszeit/);
    expect(apiSrc).toMatch(/\/spritzguss\/zykluszeit\/berechnen/);
  });

  it("zeigt die Rechenschritte transparent an", () => {
    expect(pageSrc).toMatch(/Rechenschritte/);
    expect(pageSrc).toMatch(/temperaturleitfaehigkeit_m2_s/);
    expect(pageSrc).toMatch(/Temperaturquotient/);
    expect(pageSrc).toMatch(/optimale_kuehlzeit_s/);
    expect(pageSrc).toMatch(/Nebenzeiten gesamt/);
    expect(pageSrc).toMatch(/Gesamtzykluszeit/);
  });

  it("schreibt den Vorschlag erst nach Klick auf Übernehmen ins Zykluszeitfeld", () => {
    expect(pageSrc).toMatch(/uebernehmeZykluszeit/);
    expect(pageSrc).toMatch(/>\s*Übernehmen\s*<\/button>/);
    expect(pageSrc).toMatch(
      /zykluszeit_s: wert,\s*zykluszeit_quelle: "vorschlag"/,
    );
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

  it("zeigt einen Hinweis, wenn kein Vorschlag berechenbar ist", () => {
    expect(pageSrc).toMatch(/zykluszeitVorschlag\?\.hinweis/);
    expect(pageSrc).toMatch(/berechenbar/);
  });

  it("unterstützt Mehrkomponenten-Auswahl für den Hinweis", () => {
    expect(pageSrc).toMatch(/zykluszeit_komponenten/);
    expect(pageSrc).toMatch(/1-Komponenten-Spritzguss/);
  });

  it("stellt gespeicherte Werte beim Neuladen wieder her", () => {
    expect(pageSrc).toMatch(/nebenzeitenAusGespeichert/);
    expect(pageSrc).toMatch(/item\.zykluszeit_wandstaerke_mm/);
    expect(pageSrc).toMatch(/item\.zykluszeit_quelle/);
  });

  it("sendet die Zykluszeitfelder an Berechnen und Speichern", () => {
    expect(pageSrc).toMatch(/zykluszeit_quelle: form\.zykluszeit_quelle/);
    expect(pageSrc).toMatch(/zykluszeit_wandstaerke_mm: form\.zykluszeit_wandstaerke_mm/);
    expect(apiSrc).toMatch(/"zykluszeit_wandstaerke_mm"/);
    expect(apiSrc).toMatch(/"zykluszeit_nz_ausblasen_s"/);
  });
});

describe("Material-Stammdaten Thermik", () => {
  it("enthält alle sechs thermischen Kennwerte", () => {
    for (const feld of [
      "schmelzdichte_kg_m3",
      "waermekapazitaet_j_kg_k",
      "waermeleitfaehigkeit_w_m_k",
      "werkzeugtemperatur_c",
      "schmelzetemperatur_c",
      "entformungstemperatur_c",
    ]) {
      expect(materialPageSrc).toContain(feld);
    }
  });

  it("bietet Materialgruppen für die Vorbelegung", () => {
    expect(materialPageSrc).toMatch(/materialgruppe/);
    expect(materialPageSrc).toMatch(/"POM"/);
    expect(materialPageSrc).toMatch(/Richtwerte/);
  });

  it("weist auf die Trennung von Schmelz- und Feststoffdichte hin", () => {
    expect(materialPageSrc).toMatch(/nicht die Feststoffdichte/);
  });
});
