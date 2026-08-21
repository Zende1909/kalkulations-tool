// UI-Checks für Baugruppen Löschen/Archiv-Filter.

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));

describe("Baugruppen delete/archive UI", () => {
  it("hat Löschen-Button, Bestätigung und Aktiv/Archiviert-Filter", () => {
    const src = readFileSync(resolve(__dirname, "./BaugruppenPage.tsx"), "utf-8");
    expect(src).toMatch(/>\s*Löschen\s*</);
    expect(src).toMatch(/endgültig löschen/);
    expect(src).toMatch(/archivierenBaugruppe/);
    expect(src).toMatch(/listFilter === "aktiv"/);
    expect(src).toMatch(/listFilter === "archiviert"/);
    expect(src).toMatch(/Archiviert/);
    expect(src).toMatch(/aktiv: listFilter === "aktiv"/);
  });

  it("API trennt Archivieren und Löschen", () => {
    const src = readFileSync(resolve(__dirname, "../api/baugruppen.ts"), "utf-8");
    expect(src).toMatch(/archivierenBaugruppe/);
    expect(src).toMatch(/\/baugruppen\/\$\{id\}\/archivieren/);
    expect(src).toMatch(/export function deleteBaugruppe/);
  });
});
