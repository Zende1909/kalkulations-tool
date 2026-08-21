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
  it("setzt Programm und Projekt zurück, wenn der Kunde wechselt", () => {
    const next = applyCustomerProjectChange(
      { customer_id: 1, program_id: 5, project_id: 10 },
      { customer_id: 2, program_id: 5, project_id: 10 },
    );
    expect(next).toEqual({ customer_id: 2, program_id: null, project_id: null });
  });

  it("setzt Projekt zurück, wenn das Programm wechselt", () => {
    const next = applyCustomerProjectChange(
      { customer_id: 1, program_id: 5, project_id: 10 },
      { customer_id: 1, program_id: 6, project_id: 10 },
    );
    expect(next).toEqual({ customer_id: 1, program_id: 6, project_id: null });
  });

  it("behält die Auswahl, wenn nur das Projekt wechselt", () => {
    const next = applyCustomerProjectChange(
      { customer_id: 1, program_id: 5, project_id: 10 },
      { customer_id: 1, program_id: 5, project_id: 11 },
    );
    expect(next).toEqual({ customer_id: 1, program_id: 5, project_id: 11 });
  });

  it("setzt alles zurück, wenn der Kunde geleert wird", () => {
    const next = applyCustomerProjectChange(
      { customer_id: 1, program_id: 5, project_id: 10 },
      { customer_id: null, program_id: 5, project_id: 10 },
    );
    expect(next).toEqual({ customer_id: null, program_id: null, project_id: null });
  });
});

describe("hierarchySelectionRequiresIds", () => {
  it("ist false ohne Auswahl (Legacy / reine Inhaltsänderung)", () => {
    expect(
      hierarchySelectionRequiresIds({ customer_id: null, program_id: null, project_id: null }),
    ).toBe(false);
  });

  it("ist true bei teilweiser oder voller Hierarchieauswahl", () => {
    expect(
      hierarchySelectionRequiresIds({ customer_id: 1, program_id: null, project_id: null }),
    ).toBe(true);
    expect(
      hierarchySelectionRequiresIds({ customer_id: 1, program_id: 2, project_id: null }),
    ).toBe(true);
    expect(
      hierarchySelectionRequiresIds({ customer_id: 1, program_id: 2, project_id: 3 }),
    ).toBe(true);
  });
});

describe("hasCompleteHierarchySelection", () => {
  it("erfordert Kunde, Programm und Projekt", () => {
    expect(
      hasCompleteHierarchySelection({ customer_id: 1, program_id: 2, project_id: null }),
    ).toBe(false);
    expect(
      hasCompleteHierarchySelection({ customer_id: 1, program_id: 2, project_id: 3 }),
    ).toBe(true);
  });
});

describe("applyHierarchyToFormFields", () => {
  it("stellt Freitext wieder her, wenn die Hierarchie unvollständig wird", () => {
    const current = {
      name: "BG",
      kunde: "Neu",
      projekt: "NeuP",
      customer_id: 1,
      program_id: 2,
      project_id: 3,
    };
    const next = applyHierarchyToFormFields(
      current,
      { customer_id: 1, program_id: null, project_id: null },
      { kunde: "Alt", projekt: "AltP" },
    );
    expect(next.kunde).toBe("Alt");
    expect(next.projekt).toBe("AltP");
    expect(next.program_id).toBeNull();
    expect(next.project_id).toBeNull();
  });
});

describe("resolveFreitextForSave / resolveHierarchySaveFields", () => {
  it("behält geladene project_id, wenn Dropdowns geleert und Unlink nicht bestätigt", () => {
    const fields = resolveHierarchySaveFields({
      formSelection: { customer_id: null, program_id: null, project_id: null },
      loadedProjectId: 42,
      unlinkConfirmed: false,
    });
    expect(fields).toEqual({ project_id: 42, clear_project_link: false });
  });

  it("entfernt die Verknüpfung nur bei bestätigtem Unlink", () => {
    const fields = resolveHierarchySaveFields({
      formSelection: { customer_id: null, program_id: null, project_id: null },
      loadedProjectId: 42,
      unlinkConfirmed: true,
    });
    expect(fields).toEqual({ project_id: null, clear_project_link: true });
  });

  it("nutzt Legacy-Freitext ohne Hierarchie", () => {
    expect(
      resolveFreitextForSave(
        { customer_id: null, program_id: null, project_id: null },
        { kunde: "X", projekt: "Y" },
        { kunde: "LegacyK", projekt: "LegacyP" },
      ),
    ).toEqual({ kunde: "LegacyK", projekt: "LegacyP" });
  });
});

describe("isHierarchyClearedPendingUnlink", () => {
  it("erkennt geleerte Kaskade bei bestehender Verknüpfung", () => {
    expect(
      isHierarchyClearedPendingUnlink(
        { customer_id: null, program_id: null, project_id: null },
        9,
        false,
      ),
    ).toBe(true);
  });
});

describe("formatStammdatenOptionLabel / ensurePinnedEntity", () => {
  it("kennzeichnet inaktive Einträge", () => {
    expect(formatStammdatenOptionLabel("A – B", false)).toBe("A – B (inaktiv)");
    expect(formatStammdatenOptionLabel("A – B", true)).toBe("A – B");
  });

  it("pinnt fehlende Entitäten an den Listenanfang", () => {
    expect(ensurePinnedEntity([{ id: 2 }], { id: 1 })).toEqual([{ id: 1 }, { id: 2 }]);
    expect(ensurePinnedEntity([{ id: 1 }], { id: 1 })).toEqual([{ id: 1 }]);
  });
});
