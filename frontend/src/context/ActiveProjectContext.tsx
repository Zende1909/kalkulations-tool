import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  applyCustomerProjectChange,
  emptyCustomerProjectSelection,
  hasCompleteHierarchySelection,
  type CustomerProjectSelection,
} from "../components/hierarchy/customerProjectSelection";

const STORAGE_KEY = "active_project_v1";

export interface ActiveProjectListFilters {
  customerId?: number;
  programId?: number;
  projectId?: number;
}

interface ActiveProjectContextValue {
  selection: CustomerProjectSelection;
  isComplete: boolean;
  setSelection: (next: CustomerProjectSelection) => void;
  clearSelection: () => void;
  listFilters: () => ActiveProjectListFilters;
  /** Defaults for new forms when context is complete; otherwise empty. */
  formDefaults: () => CustomerProjectSelection;
}

const ActiveProjectContext = createContext<ActiveProjectContextValue | null>(null);

function readStoredSelection(): CustomerProjectSelection {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return emptyCustomerProjectSelection();
    const parsed = JSON.parse(raw) as Partial<CustomerProjectSelection>;
    return {
      customer_id: typeof parsed.customer_id === "number" ? parsed.customer_id : null,
      program_id: typeof parsed.program_id === "number" ? parsed.program_id : null,
      project_id: typeof parsed.project_id === "number" ? parsed.project_id : null,
    };
  } catch {
    return emptyCustomerProjectSelection();
  }
}

function writeStoredSelection(selection: CustomerProjectSelection): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(selection));
  } catch {
    // ignore quota / private mode
  }
}

export function ActiveProjectProvider({ children }: { children: ReactNode }) {
  const [selection, setSelectionState] = useState<CustomerProjectSelection>(() =>
    readStoredSelection(),
  );

  const setSelection = useCallback((next: CustomerProjectSelection) => {
    setSelectionState((current) => {
      const applied = applyCustomerProjectChange(current, next);
      writeStoredSelection(applied);
      return applied;
    });
  }, []);

  const clearSelection = useCallback(() => {
    const empty = emptyCustomerProjectSelection();
    writeStoredSelection(empty);
    setSelectionState(empty);
  }, []);

  const isComplete = hasCompleteHierarchySelection(selection);

  const listFilters = useCallback((): ActiveProjectListFilters => {
    if (!hasCompleteHierarchySelection(selection)) return {};
    return {
      customerId: selection.customer_id!,
      programId: selection.program_id!,
      projectId: selection.project_id!,
    };
  }, [selection]);

  const formDefaults = useCallback((): CustomerProjectSelection => {
    if (!hasCompleteHierarchySelection(selection)) {
      return emptyCustomerProjectSelection();
    }
    return { ...selection };
  }, [selection]);

  const value = useMemo(
    () => ({
      selection,
      isComplete,
      setSelection,
      clearSelection,
      listFilters,
      formDefaults,
    }),
    [selection, isComplete, setSelection, clearSelection, listFilters, formDefaults],
  );

  return (
    <ActiveProjectContext.Provider value={value}>{children}</ActiveProjectContext.Provider>
  );
}

export function useActiveProject(): ActiveProjectContextValue {
  const ctx = useContext(ActiveProjectContext);
  if (!ctx) {
    throw new Error("useActiveProject must be used within ActiveProjectProvider");
  }
  return ctx;
}
