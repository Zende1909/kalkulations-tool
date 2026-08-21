// UI-Checks für Baugruppen: Reaktivierung, Hierarchie-Kaskade, Jahresstückzahl.

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pageSrc = readFileSync(resolve(__dirname, "./BaugruppenPage.tsx"), "utf-8");
const selectorSrc = readFileSync(
  resolve(__dirname, "../components/hierarchy/CustomerProjectSelector.tsx"),
  "utf-8",
);

describe("Baugruppen reactivation / hierarchy / Jahresstückzahl UI", () => {
  it("erlaubt Status Aktiv bei archivierten Baugruppen und reaktiviert nur bewusst", () => {
    expect(pageSrc).toMatch(/reactivating/);
    expect(pageSrc).toMatch(/status === "aktiv"/);
    expect(pageSrc).toMatch(/Zum Reaktivieren/);
    expect(pageSrc).toMatch(/Ohne Statusänderung bleibt die/);
    // Kein blindes aktiv: true beim Speichern archivierter Datensätze
    expect(pageSrc).toMatch(/aktiv: _omitAktiv/);
  });

  it("zeigt Kunde → Programm → Projekt Kaskade", () => {
    expect(selectorSrc).toMatch(/>Kunde</);
    expect(selectorSrc).toMatch(/>Programm</);
    expect(selectorSrc).toMatch(/>Projekt</);
    expect(selectorSrc).toMatch(/formatStammdatenOptionLabel/);
    expect(selectorSrc).toMatch(/listPrograms/);
    expect(selectorSrc).toMatch(/value\.customer_id == null/);
    expect(selectorSrc).toMatch(/value\.program_id == null/);
  });

  it("Jahresstückzahl ist schreibgeschützt und kommt aus dem Projekt-API", () => {
    expect(pageSrc).toMatch(/getAverageJahresstueckzahl/);
    expect(pageSrc).toMatch(/data-testid="baugruppe-jahresstueckzahl"/);
    expect(pageSrc).toMatch(/readOnly/);
    expect(pageSrc).not.toMatch(/setField\("jahresstueckzahl"/);
    expect(pageSrc).toMatch(/keine Jahresstückzahlen hinterlegt/);
  });
});
