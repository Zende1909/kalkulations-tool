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
    expect(pageSrc).toMatch(/assemblies\.reactivateHint|assemblies\.archivedHint/);
    // Kein blindes aktiv: true beim Speichern archivierter Datensätze
    expect(pageSrc).toMatch(/aktiv: _omitAktiv/);
  });

  it("zeigt Kunde → Programm → Projekt Kaskade", () => {
    expect(selectorSrc).toMatch(/project\.customer/);
    expect(selectorSrc).toMatch(/project\.program/);
    expect(selectorSrc).toMatch(/project\.project/);
    expect(selectorSrc).toMatch(/formatStammdatenOptionLabel/);
    expect(selectorSrc).toMatch(/listPrograms/);
    expect(selectorSrc).toMatch(/value\.customer_id == null/);
    expect(selectorSrc).toMatch(/value\.program_id == null/);
  });

  it("zeigt Land → Werk Kaskade neben Kundenhierarchie", () => {
    expect(pageSrc).toMatch(/assemblies\.countryRegion/);
    expect(pageSrc).toMatch(/assemblies\.plantSite/);
    expect(pageSrc).toMatch(/filteredWerke/);
    expect(pageSrc).toMatch(/selectedLandId/);
    expect(pageSrc).toMatch(/werk_id: null/);
    expect(pageSrc).toMatch(/assemblies\.inactiveTag/);
    expect(pageSrc).toMatch(/api\.get<Land\[\]>\("\/laender"\)/);
    expect(pageSrc).toMatch(/api\.get<Werk\[\]>\("\/werke"\)/);
  });
});
