import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

describe("Frontend Design System", () => {
  it("definiert zentrale UI-Komponenten und Theme-Klassen", () => {
    const css = readFileSync(resolve(__dirname, "../../index.css"), "utf-8");
    const sidebar = readFileSync(resolve(__dirname, "../layout/Sidebar.tsx"), "utf-8");
    const grid = readFileSync(resolve(__dirname, "../stammdaten/StammdatenGrid.tsx"), "utf-8");
    const materialien = readFileSync(
      resolve(__dirname, "../../pages/stammdaten/MaterialienPage.tsx"),
      "utf-8",
    );

    expect(css).toMatch(/ag-theme-kalkulation/);
    expect(css).toMatch(/app-card/);
    expect(sidebar).toMatch(/bg-sidebar-active/);
    expect(grid).toMatch(/PageHeader/);
    expect(grid).toMatch(/ag-theme-kalkulation/);
    expect(materialien).toMatch(/activeStatusCellRenderer/);
    expect(materialien).toMatch(/numericColumn/);
  });
});
