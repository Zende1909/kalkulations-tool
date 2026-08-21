import { useEffect, useState } from "react";

import { getCustomer, getProject, listCustomers, listProjects } from "../../api/hierarchy";
import type { Customer, Project } from "../../types/hierarchy";
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
  const [projects, setProjects] = useState<Project[]>([]);
  const [customersLoading, setCustomersLoading] = useState(true);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [customersError, setCustomersError] = useState<string | null>(null);
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
      setProjects([]);
      setProjectsError(null);
      setProjectsLoading(false);
      return;
    }

    setProjectsLoading(true);
    setProjectsError(null);

    (async () => {
      try {
        const active = await listProjects({ customerId: value.customer_id!, active: true });
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
  }, [value.customer_id, value.project_id]);

  return (
    <div className="grid gap-3 md:grid-cols-2 md:col-span-2">
      {legacyText && (legacyText.kunde || legacyText.projekt) && value.project_id == null && (
        <div className="md:col-span-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">Historische Freitext-Zuordnung</p>
          <p>Kunde: {legacyText.kunde || "–"}</p>
          <p>Projekt: {legacyText.projekt || "–"}</p>
          <p className="mt-1 text-xs">
            Inhaltsänderungen können ohne neue Auswahl gespeichert werden. Optional Kunde und Projekt aus
            den Stammdaten neu zuordnen.
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
            onChange(applyCustomerProjectChange(value, { customer_id: cid, project_id: null }));
          }}
        >
          <option value="">– auswählen –</option>
          {customers.map((c) => (
            <option key={c.id} value={c.id}>
              {formatStammdatenOptionLabel(`${c.customer_number} – ${c.name}`, c.active)}
            </option>
          ))}
        </select>
        {customersLoading && <p className="mt-1 text-xs text-gray-500">Kunden werden geladen…</p>}
        {customersError && <p className="mt-1 text-xs text-red-600">{customersError}</p>}
        {!customersLoading && !customersError && customers.length === 0 && (
          <p className="mt-1 text-xs text-amber-800">
            Noch keine Kunden vorhanden. Bitte zuerst unter Stammdaten anlegen.
          </p>
        )}
      </label>

      <label className="block text-sm">
        <span className="font-medium text-gray-700">Projekt</span>
        <select
          disabled={disabled || value.customer_id == null || projectsLoading}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          value={value.project_id ?? ""}
          onChange={(e) => {
            const prid = e.target.value ? Number(e.target.value) : null;
            onChange(
              applyCustomerProjectChange(value, {
                customer_id: value.customer_id,
                project_id: prid,
              }),
            );
          }}
        >
          <option value="">– auswählen –</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {formatStammdatenOptionLabel(`${p.project_number} – ${p.name}`, p.active)}
            </option>
          ))}
        </select>
        {value.customer_id == null && (
          <p className="mt-1 text-xs text-gray-500">Zuerst einen Kunden auswählen.</p>
        )}
        {value.customer_id != null && projectsLoading && (
          <p className="mt-1 text-xs text-gray-500">Projekte werden geladen…</p>
        )}
        {projectsError && <p className="mt-1 text-xs text-red-600">{projectsError}</p>}
        {value.customer_id != null && !projectsLoading && !projectsError && projects.length === 0 && (
          <p className="mt-1 text-xs text-amber-800">
            Keine Projekte für diesen Kunden. Bitte zuerst unter Stammdaten anlegen.
          </p>
        )}
      </label>
    </div>
  );
}
