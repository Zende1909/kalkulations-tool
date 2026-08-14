import { useEffect, useMemo, useState } from "react";

import {
  getCalculatedProjectVolume,
  listAvailableYears,
  listCustomers,
  listProgramVolumes,
  listPrograms,
  listProjects,
} from "../../api/hierarchy";
import type { Customer, Program, Project } from "../../types/hierarchy";

export interface HierarchySelection {
  customer_id: number | null;
  program_id: number | null;
  project_id: number | null;
  calculation_year: number | null;
  project_volume: number | null;
  jahresstueckzahl: number;
}

interface Props {
  value: HierarchySelection;
  onChange: (next: HierarchySelection) => void;
  disabled?: boolean;
  legacyText?: { kunde: string; projekt: string; jahresstueckzahl: number } | null;
}

const emptySelection = (): HierarchySelection => ({
  customer_id: null,
  program_id: null,
  project_id: null,
  calculation_year: null,
  project_volume: null,
  jahresstueckzahl: 0,
});

export function HierarchySelector({ value, onChange, disabled, legacyText }: Props) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);

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
      setYears([]);
      return;
    }
    listProjects(value.program_id).then(setProjects).catch(() => setProjects([]));
    listAvailableYears(value.program_id).then(setYears).catch(() => setYears([]));
  }, [value.program_id]);

  useEffect(() => {
    if (value.project_id == null) {
      setSelectedProject(null);
      return;
    }
    const p = projects.find((x) => x.id === value.project_id) ?? null;
    setSelectedProject(p);
  }, [value.project_id, projects]);

  useEffect(() => {
    if (
      value.project_id == null ||
      value.calculation_year == null ||
      legacyText != null
    ) {
      return;
    }
    getCalculatedProjectVolume(value.project_id, value.calculation_year)
      .then((r: { project_volume: number }) => {
        onChange({
          ...value,
          customer_id: value.customer_id,
          program_id: value.program_id,
          project_volume: r.project_volume,
          jahresstueckzahl: Math.round(r.project_volume),
        });
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value.project_id, value.calculation_year, legacyText]);

  const yearVolumes = useMemo(() => {
    if (!selectedProject || years.length === 0) return [];
    return years;
  }, [selectedProject, years]);

  if (legacyText) {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        <p className="font-medium">Historische Kalkulation (Freitext)</p>
        <p>Kunde: {legacyText.kunde || "–"}</p>
        <p>Projekt: {legacyText.projekt || "–"}</p>
        <p>Jahresstückzahl: {legacyText.jahresstueckzahl.toLocaleString("de-DE")}</p>
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

      <label className="block text-sm">
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
              calculation_year: null,
              project_volume: null,
              jahresstueckzahl: 0,
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

      <label className="block text-sm">
        <span className="font-medium text-gray-700">Kalkulationsjahr *</span>
        <select
          disabled={disabled || value.project_id == null}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          value={value.calculation_year ?? ""}
          onChange={(e) => {
            const year = e.target.value ? Number(e.target.value) : null;
            onChange({
              ...value,
              calculation_year: year,
              project_volume: null,
              jahresstueckzahl: 0,
            });
          }}
        >
          <option value="">– auswählen –</option>
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
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

      <label className="block text-sm">
        <span className="font-medium text-gray-700">Projektstückzahl (berechnet)</span>
        <input
          readOnly
          className="mt-1 w-full rounded-md border border-gray-200 bg-gray-50 px-3 py-2"
          value={
            value.project_volume != null
              ? value.project_volume.toLocaleString("de-DE")
              : "–"
          }
        />
      </label>

      <label className="block text-sm">
        <span className="font-medium text-gray-700">Jahresstückzahl (aus Projekt)</span>
        <input
          readOnly
          className="mt-1 w-full rounded-md border border-gray-200 bg-gray-50 px-3 py-2"
          value={value.jahresstueckzahl.toLocaleString("de-DE")}
        />
      </label>

      {yearVolumes.length > 0 && selectedProject && (
        <div className="md:col-span-2 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr className="border-b text-left text-gray-600">
                <th className="py-1 pr-3">Jahr</th>
                <th className="py-1 pr-3">Fahrzeugstückzahl</th>
                <th className="py-1 pr-3">Anzahl/Fzg.</th>
                <th className="py-1">Projektstückzahl</th>
              </tr>
            </thead>
            <tbody>
              {yearVolumes.map((y) => (
                <YearVolumePreviewRow
                  key={y}
                  projectId={selectedProject.id}
                  year={y}
                  qty={selectedProject.quantity_per_vehicle}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function YearVolumePreviewRow({
  projectId,
  year,
  qty,
}: {
  projectId: number;
  year: number;
  qty: number;
}) {
  const [row, setRow] = useState<{ vehicle: number; project: number } | null>(null);
  useEffect(() => {
    getCalculatedProjectVolume(projectId, year)
      .then((r: { vehicle_volume: number; project_volume: number }) =>
        setRow({ vehicle: r.vehicle_volume, project: r.project_volume }),
      )
      .catch(() => setRow(null));
  }, [projectId, year]);
  if (!row) return null;
  return (
    <tr className="border-b border-gray-100">
      <td className="py-1 pr-3">{year}</td>
      <td className="py-1 pr-3">{row.vehicle.toLocaleString("de-DE")}</td>
      <td className="py-1 pr-3">{qty}</td>
      <td className="py-1">{row.project.toLocaleString("de-DE")}</td>
    </tr>
  );
}

export async function loadProgramVolumesForPreview(programId: number) {
  return listProgramVolumes(programId);
}
