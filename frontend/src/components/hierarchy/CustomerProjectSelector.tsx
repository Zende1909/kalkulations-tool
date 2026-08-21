import { useEffect, useState } from "react";

import {
  getCustomer,
  getProgram,
  getProject,
  listCustomers,
  listPrograms,
  listProjects,
} from "../../api/hierarchy";
import type { Customer, Program, Project } from "../../types/hierarchy";
import {
  applyCustomerProjectChange,
  ensurePinnedEntity,
  formatStammdatenOptionLabel,
  type CustomerProjectSelection,
} from "./customerProjectSelection";

export type { CustomerProjectSelection };

interface Props {
  value: CustomerProjectSelection;
  onChange: (next: CustomerProjectSelection) => void;
  disabled?: boolean;
  legacyText?: { kunde: string; projekt: string } | null;
}

export function CustomerProjectSelector({ value, onChange, disabled, legacyText }: Props) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [customersLoading, setCustomersLoading] = useState(true);
  const [programsLoading, setProgramsLoading] = useState(false);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [customersError, setCustomersError] = useState<string | null>(null);
  const [programsError, setProgramsError] = useState<string | null>(null);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCustomersLoading(true);
    setCustomersError(null);

    (async () => {
      try {
        const active = await listCustomers(undefined, true);
        let next = active;
        if (value.customer_id != null && !active.some((c) => c.id === value.customer_id)) {
          try {
            const pinned = await getCustomer(value.customer_id);
            next = ensurePinnedEntity(active, pinned);
          } catch {
            // Aktuelle ID bleibt im value; Liste zeigt nur aktive.
          }
        }
        if (!cancelled) setCustomers(next);
      } catch (err) {
        if (!cancelled) {
          setCustomers([]);
          setCustomersError(err instanceof Error ? err.message : "Kunden konnten nicht geladen werden.");
        }
      } finally {
        if (!cancelled) setCustomersLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [value.customer_id]);

  useEffect(() => {
    let cancelled = false;
    if (value.customer_id == null) {
      setPrograms([]);
      setProgramsError(null);
      setProgramsLoading(false);
      return;
    }

    setProgramsLoading(true);
    setProgramsError(null);

    (async () => {
      try {
        const active = await listPrograms(value.customer_id!, undefined, true);
        let next = active;
        if (value.program_id != null && !active.some((p) => p.id === value.program_id)) {
          try {
            const pinned = await getProgram(value.program_id);
            next = ensurePinnedEntity(active, pinned);
          } catch {
            // Aktuelle ID bleibt im value.
          }
        }
        if (!cancelled) setPrograms(next);
      } catch (err) {
        if (!cancelled) {
          setPrograms([]);
          setProgramsError(err instanceof Error ? err.message : "Programme konnten nicht geladen werden.");
        }
      } finally {
        if (!cancelled) setProgramsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [value.customer_id, value.program_id]);

  useEffect(() => {
    let cancelled = false;
    if (value.program_id == null) {
      setProjects([]);
      setProjectsError(null);
      setProjectsLoading(false);
      return;
    }

    setProjectsLoading(true);
    setProjectsError(null);

    (async () => {
      try {
        const active = await listProjects({ programId: value.program_id!, active: true });
        let next = active;
        if (value.project_id != null && !active.some((p) => p.id === value.project_id)) {
          try {
            const pinned = await getProject(value.project_id);
            next = ensurePinnedEntity(active, pinned);
          } catch {
            // Aktuelle ID bleibt im value.
          }
        }
        if (!cancelled) setProjects(next);
      } catch (err) {
        if (!cancelled) {
          setProjects([]);
          setProjectsError(err instanceof Error ? err.message : "Projekte konnten nicht geladen werden.");
        }
      } finally {
        if (!cancelled) setProjectsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [value.program_id, value.project_id]);

  const emit = (partial: Partial<CustomerProjectSelection>) => {
    onChange(
      applyCustomerProjectChange(value, {
        customer_id: partial.customer_id !== undefined ? partial.customer_id : value.customer_id,
        program_id: partial.program_id !== undefined ? partial.program_id : value.program_id,
        project_id: partial.project_id !== undefined ? partial.project_id : value.project_id,
      }),
    );
  };

  return (
    <div className="grid gap-3 md:grid-cols-2 md:col-span-2">
      {legacyText && (legacyText.kunde || legacyText.projekt) && value.project_id == null && (
        <div className="md:col-span-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">Historische Freitext-Zuordnung</p>
          <p>Kunde: {legacyText.kunde || "–"}</p>
          <p>Projekt: {legacyText.projekt || "–"}</p>
          <p className="mt-1 text-xs">
            Inhaltsänderungen können ohne neue Auswahl gespeichert werden. Optional Kunde, Programm und
            Projekt aus den Stammdaten neu zuordnen.
          </p>
        </div>
      )}

      <label className="block text-sm">
        <span className="font-medium text-gray-700">Kunde</span>
        <select
          disabled={disabled || customersLoading}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          value={value.customer_id ?? ""}
          onChange={(e) => {
            const cid = e.target.value ? Number(e.target.value) : null;
            emit({ customer_id: cid, program_id: null, project_id: null });
          }}
        >
          <option value="">– auswählen –</option>
          {customers.map((c) => (
            <option key={c.id} value={c.id}>
              {formatStammdatenOptionLabel(`${c.customer_number} – ${c.name}`, c.active)}
            </option>
          ))}
        </select>
        {customersError && <p className="mt-1 text-xs text-red-600">{customersError}</p>}
      </label>

      <label className="block text-sm">
        <span className="font-medium text-gray-700">Programm</span>
        <select
          disabled={disabled || value.customer_id == null || programsLoading}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          value={value.program_id ?? ""}
          onChange={(e) => {
            const pid = e.target.value ? Number(e.target.value) : null;
            emit({ program_id: pid, project_id: null });
          }}
        >
          <option value="">– auswählen –</option>
          {programs.map((p) => (
            <option key={p.id} value={p.id}>
              {formatStammdatenOptionLabel(`${p.program_number} – ${p.name}`, p.active)}
            </option>
          ))}
        </select>
        {programsError && <p className="mt-1 text-xs text-red-600">{programsError}</p>}
      </label>

      <label className="block text-sm md:col-span-2">
        <span className="font-medium text-gray-700">Projekt</span>
        <select
          disabled={disabled || value.program_id == null || projectsLoading}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          value={value.project_id ?? ""}
          onChange={(e) => {
            const prid = e.target.value ? Number(e.target.value) : null;
            emit({ project_id: prid });
          }}
        >
          <option value="">– auswählen –</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {formatStammdatenOptionLabel(`${p.project_number} – ${p.name}`, p.active)}
            </option>
          ))}
        </select>
        {projectsError && <p className="mt-1 text-xs text-red-600">{projectsError}</p>}
      </label>
    </div>
  );
}
