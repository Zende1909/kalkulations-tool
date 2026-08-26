// UI-Checks: Maschinenmaske – Scroll-Modal, Werkpflicht, keine Werk-Parameter-Felder.

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./MaschinenPage.tsx"), "utf-8");
const modalSrc = readFileSync(
  resolve(__dirname, "../../components/stammdaten/StammdatenFormModal.tsx"),
  "utf-8",
);
const werkeSrc = readFileSync(resolve(__dirname, "./WerkePage.tsx"), "utf-8");

describe("Maschinen-Stammdatenmaske Plant-Costing UI", () => {
  it("Modal hat begrenzte Höhe und scrollbaren Inhalt mit festem Kopf/Fuß", () => {
    expect(modalSrc).toMatch(/max-h-\[min\(92dvh/);
    expect(modalSrc).toMatch(/overflow-y-auto/);
    expect(modalSrc).toMatch(/shrink-0/);
    expect(modalSrc).toMatch(/<header/);
    expect(modalSrc).toMatch(/<footer/);
  });

  it("Werk ist Pflicht und zeigt inaktive Zuordnung", () => {
    expect(pageSrc).toMatch(/Werk wählen/);
    expect(pageSrc).toMatch(/required: true/);
    expect(pageSrc).toMatch(/\(inaktiv\)/);
    expect(pageSrc).toMatch(/w\.aktiv/);
  });

  it("werksspezifische Felder fehlen als editierbare Formularfelder", () => {
    for (const name of [
      "arbeitstage_pro_jahr",
      "schichten_pro_tag",
      "stunden_pro_schicht",
      "oee",
      "space_cost_satz_pro_sqm_jahr",
      "abschreibungsdauer_jahre",
      "zinssatz",
      "versicherungssatz",
      "instandhaltungssatz",
      "strompreis",
      "druckluftpreis",
      "kuehlwasserpreis",
    ]) {
      expect(pageSrc).not.toMatch(new RegExp(`name:\\s*"${name}"`));
    }
    expect(pageSrc).not.toMatch(/label: "Arbeitstage/);
    expect(pageSrc).not.toMatch(/label: "Strompreis"/);
  });

  it("maschinenabhängige Felder und Readonly-Stundensatz bleiben", () => {
    expect(pageSrc).toMatch(/Investment/);
    expect(pageSrc).toMatch(/Schließkraft/);
    expect(pageSrc).toMatch(/Setup-Zeit/);
    expect(pageSrc).toMatch(/Setup-Mitarbeiteranzahl/);
    expect(pageSrc).toMatch(/Stromverbrauch/);
    expect(pageSrc).toMatch(/readOnly: true/);
    expect(pageSrc).toMatch(/Stundensatz \(EUR\/h\)/);
    expect(pageSrc).toMatch(/Kostenparameter werden aus Werk/);
  });

  it("Werk-Stammdaten pflegen die Standortparameter", () => {
    expect(werkeSrc).toMatch(/Arbeitstage\/Jahr/);
    expect(werkeSrc).toMatch(/Space-Satz/);
    expect(werkeSrc).toMatch(/Strompreis/);
    expect(werkeSrc).toMatch(/oee/);
  });
});
