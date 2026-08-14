import { useEffect, useState } from "react";

import {
  getProjectVolumeProfile,
  listCustomers,
  listPrograms,
  listProjects,
} from "../../api/hierarchy";
import type { Customer, Program, Project, ProjectVolumeProfile } from "../../types/hierarchy";

export interface HierarchySelection {
  customer_id: number | null;
  program_id: number | null;
  project_id: number | null;
}

interface Props {
  value: HierarchySelection;
  onChange: (next: HierarchySelection) => void;
  disabled?: boolean;
  legacyText?: { kunde: string; projekt: string; jahresstueckzahl: number; calculation_year?: number | null } | null;
}

const emptySelection = (): HierarchySelection => ({
  customer_id: null,
  program_id: null,
  project_id: null,
});

export function HierarchySelector({ value, onChange, disabled, legacyText }: Props) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [volumeProfile, setVolumeProfile] = useState<ProjectVolumeProfile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);

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

  useEffect(() => {
    if (value.project_id == null) {
      setSelectedProject(null);
      setVolumeProfile(null);
      return;
    }
    const p = projects.find((x) => x.id === value.project_id) ?? null;
    setSelectedProject(p);
    setProfileError(null);
    getProjectVolumeProfile(value.project_id)
      .then(setVolumeProfile)
      .catch((err) => {
        setVolumeProfile(null);
        setProfileError(err instanceof Error ? err.message : "Mengenprofil konnte nicht geladen werden.");
      });
  }, [value.project_id, projects]);

  if (legacyText) {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        <p className="font-medium">Historische Kalkulation (Freitext)</p>
        <p>Kunde: {legacyText.kunde || "–"}</p>
        <p>Projekt: {legacyText.projekt || "–"}</p>
        {legacyText.calculation_year != null && (
          <p>Kalkulationsjahr: {legacyText.calculation_year}</p>
        )}
        <p>Jahresstückzahl (historisch): {legacyText.jahresstueckzahl.toLocaleString("de-DE")}</p>
      </div>
    );
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <label className="block text-sm">
        <span className="font-medium text-gray-700">Kunde *</span>
        <select
          disabled={disabled}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          value={value.customer_id ?? ""}
          onChange={(e) => {
            const cid = e.target.value ? Number(e.target.value) : null;
            onChange({ ...emptySelection(), customer_id: cid });
          }}
        >
          <option value="">– auswählen –</option>
          {customers.map((c) => (
            <option key={c.id} value={c.id}>
              {c.customer_number} – {c.name}
            </option>
          ))}
        </select>
      </label>

      <label className="block text-sm">
        <span className="font-medium text-gray-700">Programm *</span>
        <select
          disabled={disabled || value.customer_id == null}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          value={value.program_id ?? ""}
          onChange={(e) => {
            const pid = e.target.value ? Number(e.target.value) : null;
            onChange({
              ...emptySelection(),
              customer_id: value.customer_id,
              program_id: pid,
            });
          }}
        >
          <option value="">– auswählen –</option>
          {programs.map((p) => (
            <option key={p.id} value={p.id}>
              {p.program_number} – {p.name}
            </option>
          ))}
        </select>
      </label>

      <label className="block text-sm md:col-span-2">
        <span className="font-medium text-gray-700">Projekt *</span>
        <select
          disabled={disabled || value.program_id == null}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          value={value.project_id ?? ""}
          onChange={(e) => {
            const prid = e.target.value ? Number(e.target.value) : null;
            const proj = projects.find((p) => p.id === prid);
            onChange({
              customer_id: value.customer_id,
              program_id: value.program_id,
              project_id: prid,
            });
            setSelectedProject(proj ?? null);
          }}
        >
          <option value="">– auswählen –</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.project_number} – {p.name}
            </option>
          ))}
        </select>
      </label>

      {selectedProject && (
        <div className="md:col-span-2 rounded-md bg-slate-50 p-3 text-sm text-slate-800">
          <p>
            Bauteilbereich: <strong>{selectedProject.component_area}</strong> · Anzahl pro Fahrzeug:{" "}
            <strong>{selectedProject.quantity_per_vehicle}</strong>
          </p>
        </div>
      )}

      {profileError && (
        <div className="md:col-span-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {profileError}
        </div>
      )}

      {volumeProfile && volumeProfile.rows.length > 0 && (
        <div className="md:col-span-2">
          <h4 className="mb-2 text-sm font-semibold text-gray-800">
            Projektstückzahlen über die Projektlaufzeit
          </h4>
          <div className="overflow-x-auto rounded-md border border-gray-200">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 text-left text-gray-600">
                  <th className="px-3 py-2">Jahr</th>
                  <th className="px-3 py-2">Programmfahrzeuge</th>
                  <th className="px-3 py-2">Anzahl pro Fahrzeug</th>
                  <th className="px-3 py-2">Projektstückzahl</th>
                </tr>
              </thead>
              <tbody>
                {volumeProfile.rows.map((row) => (
                  <tr key={row.calendar_year} className="border-b border-gray-100">
                    <td className="px-3 py-2">{row.calendar_year}</td>
                    <td className="px-3 py-2">{row.vehicle_volume.toLocaleString("de-DE")}</td>
                    <td className="px-3 py-2">{row.quantity_per_vehicle}</td>
                    <td className="px-3 py-2">{row.project_volume.toLocaleString("de-DE")}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-slate-50 font-medium">
                  <td className="px-3 py-2" colSpan={3}>
                    Gesamt über die Laufzeit
                  </td>
                  <td className="px-3 py-2">
                    {volumeProfile.total_project_volume.toLocaleString("de-DE")}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          <p className="mt-1 text-xs text-gray-500">
            Nur zur Information – der Teilepreis gilt für die gesamte Projektlaufzeit.
          </p>
        </div>
      )}
    </div>
  );
}
