import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const pageSrc = readFileSync(resolve(__dirname, "./SpritzgussPage.tsx"), "utf-8");
const savedListSrc = readFileSync(
  resolve(__dirname, "../components/spritzguss/SpritzgussSavedList.tsx"),
  "utf-8",
);
const apiSrc = readFileSync(resolve(__dirname, "../api/spritzguss.ts"), "utf-8");

describe("Einzelteilkalkulation Teilbild & gespeicherte Liste", () => {
  it("bindet Teilbild-Upload und Vorschau ein", () => {
    expect(pageSrc).toMatch(/TeilbildField/);
    expect(pageSrc).toMatch(/teilbild_mime/);
    expect(pageSrc).toMatch(/teilbildPreview/);
  });

  it("nutzt verbesserte gespeicherte Liste mit Filter", () => {
    expect(pageSrc).toMatch(/SpritzgussSavedList/);
    expect(savedListSrc).toMatch(/Gespeicherte Kalkulationen/);
    expect(savedListSrc).toMatch(/Kunde/);
    expect(savedListSrc).toMatch(/Programm/);
    expect(savedListSrc).toMatch(/Projekt/);
    expect(savedListSrc).toMatch(/teilbildSrc/);
  });

  it("filtert Liste serverseitig nach Hierarchie", () => {
    expect(apiSrc).toMatch(/customer_id/);
    expect(apiSrc).toMatch(/program_id/);
    expect(apiSrc).toMatch(/project_id/);
  });
});
