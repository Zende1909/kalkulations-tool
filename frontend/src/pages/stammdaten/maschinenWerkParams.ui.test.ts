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
    expect(pageSrc).toMatch(/masterData\.selectPlant/);
    expect(pageSrc).toMatch(/required: true/);
    expect(pageSrc).toMatch(/masterData\.plantInactive/);
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
    expect(pageSrc).toMatch(/masterData\.investment/);
    expect(pageSrc).toMatch(/masterData\.clampingForceT/);
    expect(pageSrc).toMatch(/masterData\.setupTimeMin/);
    expect(pageSrc).toMatch(/masterData\.setupOperators/);
    expect(pageSrc).toMatch(/masterData\.powerConsumption/);
    expect(pageSrc).toMatch(/readOnly: true/);
    expect(pageSrc).toMatch(/masterData\.hourlyRateEurH/);
    expect(pageSrc).toMatch(/masterData\.plantParamsBanner/);
  });

  it("Werk-Stammdaten pflegen die Standortparameter", () => {
    expect(werkeSrc).toMatch(/masterData\.workdaysPerYear/);
    expect(werkeSrc).toMatch(/masterData\.spaceCostRate/);
    expect(werkeSrc).toMatch(/masterData\.electricityPrice/);
    expect(werkeSrc).toMatch(/oee/);
  });
});
