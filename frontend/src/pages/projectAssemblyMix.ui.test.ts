import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const pageSrc = readFileSync(resolve(__dirname, "./BaugruppenPage.tsx"), "utf-8");
const apiSrc = readFileSync(resolve(__dirname, "../api/baugruppen.ts"), "utf-8");
const typesSrc = readFileSync(resolve(__dirname, "../types/projectAssemblyMix.ts"), "utf-8");
const navSrc = readFileSync(resolve(__dirname, "../components/layout/navConfig.ts"), "utf-8");
const appSrc = readFileSync(resolve(__dirname, "../App.tsx"), "utf-8");

describe("Project assembly mix UI", () => {
  it("exposes Anteil am Projekt on BaugruppenPage", () => {
    expect(pageSrc).toMatch(/Anteil am Projekt/);
    expect(pageSrc).toMatch(/variant_share_pct/);
    expect(pageSrc).toMatch(/clear_variant_share/);
  });

  it("uses project-mix API client", () => {
    expect(apiSrc).toMatch(/getProjectAssemblyMix/);
    expect(apiSrc).toMatch(/\/baugruppen\/project-mix/);
    expect(pageSrc).toMatch(/getProjectAssemblyMix/);
  });

  it("has no Baugruppenfamilien nav entry", () => {
    expect(navSrc).not.toMatch(/Baugruppenfamilien/);
    expect(appSrc).toMatch(/Navigate to=\"\/baugruppen\"/);
  });

  it("shows mix status as vollständig/unvollständig text", () => {
    expect(pageSrc).toMatch(/mixStatusLabel|vollständig/);
    expect(typesSrc).toMatch(/vollständig/);
    expect(typesSrc).toMatch(/unvollständig/);
    expect(pageSrc).toMatch(/ProjectAssemblyMix|projectMix/);
  });
});
