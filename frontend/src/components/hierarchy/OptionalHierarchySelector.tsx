import { useEffect, useState } from "react";

import { listCustomers, listPrograms, listProjects } from "../../api/hierarchy";
import type { Customer, Program, Project } from "../../types/hierarchy";
import type { HierarchySelection } from "./HierarchySelector";

interface Props {
  value: HierarchySelection;
  onChange: (next: HierarchySelection) => void;
  disabled?: boolean;
}

const emptySelection = (): HierarchySelection => ({
  customer_id: null,
  program_id: null,
  project_id: null,
});

/** Optionale Kunde → Programm → Projekt-Kette (Projekt leer = Standardkaufteil). */
export function OptionalHierarchySelector({ value, onChange, disabled }: Props) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    listCustomers(undefined, true).then(setCustomers).catch(() => setCustomers([]));
  }, []);

  useEffect(() => {
    if (value.customer_id == null) {
      setPrograms([]);
      return;
    }
    listPrograms(value.customer_id).then(setPrograms).catch(() => setPrograms([]));
  }, [value.customer_id]);

  useEffect(() => {
    if (value.program_id == null) {
      setProjects([]);
      return;
    }
    listProjects(value.program_id).then(setProjects).catch(() => setProjects([]));
  }, [value.program_id]);

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">
        Ohne Projektzuordnung ist dieses Kaufteil ein Standardkaufteil und für alle Projekte
        verfügbar.
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="block text-sm">
          <span className="font-medium text-gray-700">Kunde (optional)</span>
          <select
            disabled={disabled}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
            value={value.customer_id ?? ""}
            onChange={(e) => {
              const cid = e.target.value ? Number(e.target.value) : null;
              onChange({ ...emptySelection(), customer_id: cid });
            }}
          >
            <option value="">– kein Kunde / Standardkaufteil –</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.customer_number} – {c.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          <span className="font-medium text-gray-700">Programm (optional)</span>
          <select
            disabled={disabled || value.customer_id == null}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
            value={value.program_id ?? ""}
            onChange={(e) => {
              const pid = e.target.value ? Number(e.target.value) : null;
              onChange({
                customer_id: value.customer_id,
                program_id: pid,
                project_id: null,
              });
            }}
          >
            <option value="">– kein Programm –</option>
            {programs.map((p) => (
              <option key={p.id} value={p.id}>
                {p.program_number} – {p.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm md:col-span-2">
          <span className="font-medium text-gray-700">Projekt (optional)</span>
          <select
            disabled={disabled || value.program_id == null}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
            value={value.project_id ?? ""}
            onChange={(e) => {
              const prid = e.target.value ? Number(e.target.value) : null;
              onChange({
                customer_id: value.customer_id,
                program_id: value.program_id,
                project_id: prid,
              });
            }}
          >
            <option value="">– Standardkaufteil (alle Projekte) –</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.project_number} – {p.name}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
