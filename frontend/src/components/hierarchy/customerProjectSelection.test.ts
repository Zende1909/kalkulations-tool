import { describe, expect, it } from "vitest";

import {
  applyCustomerProjectChange,
  applyHierarchyToFormFields,
  ensurePinnedEntity,
  formatStammdatenOptionLabel,
  hasCompleteHierarchySelection,
  hierarchySelectionRequiresIds,
  isHierarchyClearedPendingUnlink,
  resolveFreitextForSave,
  resolveHierarchySaveFields,
} from "./customerProjectSelection";

describe("applyCustomerProjectChange", () => {
  it("setzt die Projektauswahl zurück, wenn der Kunde wechselt", () => {
    const next = applyCustomerProjectChange(
      { customer_id: 1, project_id: 10 },
      { customer_id: 2, project_id: 10 },
    );
    expect(next).toEqual({ customer_id: 2, project_id: null });
  });

  it("behält die Projektauswahl, wenn nur das Projekt wechselt", () => {
    const next = applyCustomerProjectChange(
      { customer_id: 1, project_id: 10 },
      { customer_id: 1, project_id: 11 },
    );
    expect(next).toEqual({ customer_id: 1, project_id: 11 });
  });

  it("setzt beides zurück, wenn der Kunde geleert wird", () => {
    const next = applyCustomerProjectChange(
      { customer_id: 1, project_id: 10 },
      { customer_id: null, project_id: 10 },
    );
    expect(next).toEqual({ customer_id: null, project_id: null });
  });
});

describe("hierarchySelectionRequiresIds", () => {
  it("ist false ohne Auswahl (Legacy / reine Inhaltsänderung)", () => {
    expect(hierarchySelectionRequiresIds({ customer_id: null, project_id: null })).toBe(false);
  });

  it("ist true bei teilweiser oder voller Hierarchieauswahl", () => {
    expect(hierarchySelectionRequiresIds({ customer_id: 1, project_id: null })).toBe(true);
    expect(hierarchySelectionRequiresIds({ customer_id: null, project_id: 2 })).toBe(true);
    expect(hierarchySelectionRequiresIds({ customer_id: 1, project_id: 2 })).toBe(true);
  });
});

describe("legacy freitext across hierarchy start/abort", () => {
  const legacy = { kunde: "Freitext-Kunde", projekt: "Freitext-Projekt" };
  const base = {
    customer_id: null as number | null,
    project_id: null as number | null,
    kunde: legacy.kunde,
    projekt: legacy.projekt,
  };

  it("beginnt Hierarchieauswahl ohne Freitext zu löschen", () => {
    const mid = applyHierarchyToFormFields(base, { customer_id: 1, project_id: null }, legacy);
    expect(mid.customer_id).toBe(1);
    expect(mid.project_id).toBeNull();
    expect(mid.kunde).toBe(legacy.kunde);
    expect(mid.projekt).toBe(legacy.projekt);
    expect(hasCompleteHierarchySelection(mid)).toBe(false);
  });

  it("stellt Freitext nach Abbruch wieder her", () => {
    const mid = applyHierarchyToFormFields(base, { customer_id: 1, project_id: null }, legacy);
    const aborted = applyHierarchyToFormFields(mid, { customer_id: null, project_id: null }, legacy);
    expect(aborted).toEqual({
      customer_id: null,
      project_id: null,
      kunde: legacy.kunde,
      projekt: legacy.projekt,
    });
  });

  it("lässt Freitext bis zur vollständigen Auswahl stehen und Save nutzt Legacy ohne project_id", () => {
    const mid = applyHierarchyToFormFields(base, { customer_id: 1, project_id: null }, legacy);
    const saveText = resolveFreitextForSave(
      { customer_id: mid.customer_id, project_id: mid.project_id },
      { kunde: "", projekt: "" },
      legacy,
    );
    expect(saveText).toEqual(legacy);

    const complete = applyHierarchyToFormFields(mid, { customer_id: 1, project_id: 10 }, legacy);
    expect(hasCompleteHierarchySelection(complete)).toBe(true);
  });
});

describe("resolveProjectIdForSave / unlink", () => {
  it("stellt die geladene Verknüpfung wieder her, wenn Dropdowns versehentlich geleert wurden", () => {
    expect(
      resolveHierarchySaveFields({
        formSelection: { customer_id: null, project_id: null },
        loadedProjectId: 42,
        unlinkConfirmed: false,
      }),
    ).toEqual({ project_id: 42, clear_project_link: false });
    expect(
      isHierarchyClearedPendingUnlink({ customer_id: null, project_id: null }, 42, false),
    ).toBe(true);
  });

  it("sendet clear_project_link nach explizit bestätigtem Entfernen", () => {
    expect(
      resolveHierarchySaveFields({
        formSelection: { customer_id: null, project_id: null },
        loadedProjectId: 42,
        unlinkConfirmed: true,
      }),
    ).toEqual({ project_id: null, clear_project_link: true });
  });

  it("sendet die neue Hierarchie bei vollständiger Auswahl ohne clear-Flag", () => {
    expect(
      resolveHierarchySaveFields({
        formSelection: { customer_id: 1, project_id: 99 },
        loadedProjectId: 42,
        unlinkConfirmed: false,
      }),
    ).toEqual({ project_id: 99, clear_project_link: false });
  });

  it("belässt Legacy ohne project_id bei null ohne clear-Flag", () => {
    expect(
      resolveHierarchySaveFields({
        formSelection: { customer_id: null, project_id: null },
        loadedProjectId: null,
        unlinkConfirmed: false,
      }),
    ).toEqual({ project_id: null, clear_project_link: false });
  });
});

describe("inactive stammdaten display helpers", () => {
  it("kennzeichnet inaktive Optionen", () => {
    expect(formatStammdatenOptionLabel("C-1 – Acme", true)).toBe("C-1 – Acme");
    expect(formatStammdatenOptionLabel("C-1 – Acme", false)).toBe("C-1 – Acme (inaktiv)");
  });

  it("hängt die aktuell gesetzte inaktive Entität an die aktiven Optionen", () => {
    const active = [{ id: 2, name: "Aktiv" }];
    const pinned = { id: 1, name: "Alt", active: false };
    expect(ensurePinnedEntity(active, pinned)).toEqual([pinned, ...active]);
    expect(ensurePinnedEntity(active, { id: 2, name: "Aktiv" })).toEqual(active);
  });
});
