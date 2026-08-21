import { describe, expect, it } from "vitest";

import { normalizeListProjectsArgs } from "./hierarchy";

describe("normalizeListProjectsArgs", () => {
  it("unterstützt Legacy-Aufruf listProjects(programId, search) wie HierarchySelector", () => {
    expect(normalizeListProjectsArgs(5, "deck")).toEqual({ programId: 5, search: "deck" });
    expect(normalizeListProjectsArgs(undefined)).toEqual({ programId: undefined, search: undefined });
  });

  it("unterstützt Optionsobjekt für customer_id-Filter und active=true", () => {
    expect(normalizeListProjectsArgs({ customerId: 9, active: true })).toEqual({
      customerId: 9,
      active: true,
    });
  });
});
