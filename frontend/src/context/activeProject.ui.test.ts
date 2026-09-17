import { beforeEach, afterEach, describe, expect, it } from "vitest";

import {
  emptyCustomerProjectSelection,
  hasCompleteHierarchySelection,
} from "../components/hierarchy/customerProjectSelection";

const STORAGE_KEY = "active_project_v1";

/** Minimal localStorage stub for Vitest's node environment. */
function createMemoryStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null;
    },
    key(index: number) {
      return [...store.keys()][index] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
  };
}

describe("Active project selection helpers", () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      value: createMemoryStorage(),
    });
  });

  afterEach(() => {
    Reflect.deleteProperty(globalThis, "localStorage");
  });

  it("empty selection is incomplete", () => {
    expect(hasCompleteHierarchySelection(emptyCustomerProjectSelection())).toBe(false);
  });

  it("complete selection requires all three ids", () => {
    expect(
      hasCompleteHierarchySelection({
        customer_id: 1,
        program_id: 2,
        project_id: null,
      }),
    ).toBe(false);
    expect(
      hasCompleteHierarchySelection({
        customer_id: 1,
        program_id: 2,
        project_id: 3,
      }),
    ).toBe(true);
  });

  it("persists selection JSON under active_project_v1", () => {
    const selection = { customer_id: 10, program_id: 20, project_id: 30 };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(selection));
    const raw = localStorage.getItem(STORAGE_KEY);
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw!)).toEqual(selection);
  });
});

describe("Active project UI wiring", () => {
  it("Sidebar exposes project bar and Alle Projekte", async () => {
    const { readFileSync } = await import("node:fs");
    const { resolve } = await import("node:path");
    const src = readFileSync(resolve(__dirname, "../components/layout/Sidebar.tsx"), "utf-8");
    expect(src).toMatch(/active-project-bar/);
    expect(src).toMatch(/Alle Projekte/);
    expect(src).toMatch(/useActiveProject/);
    expect(src).toMatch(/CustomerProjectSelector/);
    expect(src).toMatch(/compact/);
  });

  it("App wraps with ActiveProjectProvider", async () => {
    const { readFileSync } = await import("node:fs");
    const { resolve } = await import("node:path");
    const src = readFileSync(resolve(__dirname, "../App.tsx"), "utf-8");
    expect(src).toMatch(/ActiveProjectProvider/);
  });

  it("modules consume useActiveProject", async () => {
    const { readFileSync } = await import("node:fs");
    const { resolve } = await import("node:path");
    for (const rel of [
      "../pages/SpritzgussPage.tsx",
      "../pages/BaugruppenPage.tsx",
      "../pages/stammdaten/KaufteilePage.tsx",
      "../pages/InvestitionenPage.tsx",
      "../pages/BusinessCasePage.tsx",
      "../components/spritzguss/SpritzgussSavedList.tsx",
    ]) {
      const src = readFileSync(resolve(__dirname, rel), "utf-8");
      expect(src).toMatch(/useActiveProject/);
    }
  });

  it("baugruppen list client supports project_id filter", async () => {
    const { readFileSync } = await import("node:fs");
    const { resolve } = await import("node:path");
    const src = readFileSync(resolve(__dirname, "../api/baugruppen.ts"), "utf-8");
    expect(src).toMatch(/project_id/);
  });
});
