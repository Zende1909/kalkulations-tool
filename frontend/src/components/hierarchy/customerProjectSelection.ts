/** Cascading Kunde → Programm → Projekt selection for Baugruppen. */

export interface CustomerProjectSelection {
  customer_id: number | null;
  program_id: number | null;
  project_id: number | null;
}

export interface LegacyFreitext {
  kunde: string;
  projekt: string;
}

export function applyCustomerProjectChange(
  current: CustomerProjectSelection,
  next: CustomerProjectSelection,
): CustomerProjectSelection {
  if (next.customer_id !== current.customer_id) {
    return { customer_id: next.customer_id, program_id: null, project_id: null };
  }
  if (next.program_id !== current.program_id) {
    return {
      customer_id: next.customer_id,
      program_id: next.program_id,
      project_id: null,
    };
  }
  return {
    customer_id: next.customer_id,
    program_id: next.program_id,
    project_id: next.project_id,
  };
}

/** Hierarchie ist nur Pflicht, wenn der Benutzer eine (Teil-)Zuordnung gewählt hat. */
export function hierarchySelectionRequiresIds(selection: CustomerProjectSelection): boolean {
  return selection.customer_id != null || selection.program_id != null || selection.project_id != null;
}

export function hasCompleteHierarchySelection(selection: CustomerProjectSelection): boolean {
  return selection.customer_id != null && selection.program_id != null && selection.project_id != null;
}

/**
 * Aktualisiert Formularfelder bei Hierarchieänderung.
 * Freitext bleibt bis zur vollständigen Auswahl erhalten bzw. wird bei Abbruch aus Legacy wiederhergestellt.
 */
export function applyHierarchyToFormFields<T extends CustomerProjectSelection & LegacyFreitext>(
  current: T,
  nextSelection: CustomerProjectSelection,
  legacyFreitext: LegacyFreitext | null,
): T {
  const selection = applyCustomerProjectChange(
    {
      customer_id: current.customer_id,
      program_id: current.program_id,
      project_id: current.project_id,
    },
    nextSelection,
  );

  if (hasCompleteHierarchySelection(selection)) {
    return { ...current, ...selection };
  }

  const freitext = legacyFreitext ?? { kunde: current.kunde, projekt: current.projekt };
  return {
    ...current,
    ...selection,
    kunde: freitext.kunde,
    projekt: freitext.projekt,
  };
}

/** Payload-Kunde/Projekt: ohne gültige Hierarchie die gemerkten Legacy-Werte bevorzugen. */
export function resolveFreitextForSave(
  selection: CustomerProjectSelection,
  formFreitext: LegacyFreitext,
  legacyFreitext: LegacyFreitext | null,
): LegacyFreitext {
  if (hasCompleteHierarchySelection(selection)) {
    return formFreitext;
  }
  if (legacyFreitext) {
    return legacyFreitext;
  }
  return formFreitext;
}

/**
 * project_id für den Save-Payload.
 * - bestätigtes Entfernen → null (clear_project_link separat)
 * - neue vollständige Auswahl → Formularwert
 * - Dropdowns geleert, aber geladene Verknüpfung vorhanden → geladene ID behalten
 * - Legacy ohne Verknüpfung → null
 */
export function resolveProjectIdForSave(options: {
  formSelection: CustomerProjectSelection;
  loadedProjectId: number | null;
  unlinkConfirmed: boolean;
}): number | null {
  const { formSelection, loadedProjectId, unlinkConfirmed } = options;
  if (unlinkConfirmed) {
    return null;
  }
  if (hasCompleteHierarchySelection(formSelection)) {
    return formSelection.project_id;
  }
  if (!hierarchySelectionRequiresIds(formSelection) && loadedProjectId != null) {
    return loadedProjectId;
  }
  return formSelection.project_id;
}

/** Hierarchie-Felder für Create/Update: unterscheidet normales Speichern und explizites Entfernen. */
export function resolveHierarchySaveFields(options: {
  formSelection: CustomerProjectSelection;
  loadedProjectId: number | null;
  unlinkConfirmed: boolean;
}): { project_id: number | null; clear_project_link: boolean } {
  if (options.unlinkConfirmed) {
    return { project_id: null, clear_project_link: true };
  }
  return {
    project_id: resolveProjectIdForSave({ ...options, unlinkConfirmed: false }),
    clear_project_link: false,
  };
}

/** Dropdowns wurden geleert, obwohl eine geladene Verknüpfung existiert (noch nicht bestätigt entfernt). */
export function isHierarchyClearedPendingUnlink(
  formSelection: CustomerProjectSelection,
  loadedProjectId: number | null,
  unlinkConfirmed: boolean,
): boolean {
  return (
    loadedProjectId != null &&
    !unlinkConfirmed &&
    formSelection.customer_id == null &&
    formSelection.program_id == null &&
    formSelection.project_id == null
  );
}

export function formatStammdatenOptionLabel(primary: string, active: boolean): string {
  return active ? primary : `${primary} (inaktiv)`;
}

/** Stellt sicher, dass die aktuell verknüpfte (ggf. inaktive) Entität in der Liste sichtbar ist. */
export function ensurePinnedEntity<T extends { id: number }>(items: T[], pinned: T | null | undefined): T[] {
  if (!pinned) return items;
  if (items.some((item) => item.id === pinned.id)) return items;
  return [pinned, ...items];
}
