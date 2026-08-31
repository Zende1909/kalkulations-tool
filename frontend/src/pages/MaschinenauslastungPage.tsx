import { useCallback, useEffect, useMemo, useState } from "react";

import { getMaschinenAuslastung } from "../api/maschinen";
import { listCustomers, listPrograms, listProjects } from "../api/hierarchy";
import { api } from "../api/client";
import type { Customer, Program, Project } from "../types/hierarchy";
import type { MaschineAuslastungResponse, MaschineAuslastungRow } from "../types/maschineAuslastung";
import type { Werk } from "../types/stammdaten";
import { formatPercentOrDash } from "./businessCaseFormatting";

type SortKey =
  | "bezeichnung"
  | "required_hours"
  | "available_hours"
  | "utilization_pct"
  | "rest_capacity_hours";

function KpiCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "positive" | "negative" | "warning" | "neutral";
}) {
  const toneClass =
    tone === "positive"
      ? "text-emerald-700"
      : tone === "negative"
        ? "text-red-700"
        : tone === "warning"
          ? "text-amber-700"
          : "text-gray-900";
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`mt-2 text-xl font-semibold ${toneClass}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-gray-500">{hint}</div>}
    </div>
  );
}

function formatHours(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function restLabel(row: MaschineAuslastungRow): string {
  if (row.is_overloaded && row.overload_hours != null) {
    return `Überlastung ${formatHours(row.overload_hours)} h`;
  }
  if (row.rest_capacity_hours != null) {
    return `${formatHours(row.rest_capacity_hours)} h`;
  }
  return "–";
}

export function MaschinenauslastungPage() {
  const [werke, setWerke] = useState<Werk[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);

  const [plantId, setPlantId] = useState<number | null>(null);
  const [customerId, setCustomerId] = useState<number | null>(null);
  const [programId, setProgramId] = useState<number | null>(null);
  const [selectedProjectIds, setSelectedProjectIds] = useState<number[]>([]);

  const [data, setData] = useState<MaschineAuslastungResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("utilization_pct");
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    api.get<Werk[]>("/werke").then(setWerke).catch(() => setWerke([]));
    listCustomers(undefined, true).then(setCustomers).catch(() => setCustomers([]));
  }, []);

  useEffect(() => {
    if (customerId == null) {
      setPrograms([]);
      return;
    }
    listPrograms(customerId, undefined, true).then(setPrograms).catch(() => setPrograms([]));
  }, [customerId]);

  useEffect(() => {
    if (programId == null) {
      setProjects([]);
      return;
    }
    listProjects(programId).then(setProjects).catch(() => setProjects([]));
  }, [programId]);

  const load = useCallback(async () => {
    if (plantId == null) {
      setError("Bitte ein Werk auswählen.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const resp = await getMaschinenAuslastung({
        plant_id: plantId,
        customer_id: customerId ?? undefined,
        program_id: programId ?? undefined,
        project_ids: selectedProjectIds,
      });
      setData(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
      setData(null);
    } finally {
      setBusy(false);
    }
  }, [plantId, customerId, programId, selectedProjectIds]);

  useEffect(() => {
    if (plantId != null) {
      void load();
    } else {
      setData(null);
    }
  }, [plantId, customerId, programId, selectedProjectIds, load]);

  const sortedMachines = useMemo(() => {
    if (!data) return [];
    const rows = [...data.machines];
    rows.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string" && typeof bv === "string") {
        return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      const na = Number(av);
      const nb = Number(bv);
      return sortAsc ? na - nb : nb - na;
    });
    return rows;
  }, [data, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(key === "bezeichnung");
    }
  };

  const toggleProject = (id: number) => {
    setSelectedProjectIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const sortIndicator = (key: SortKey) => (sortKey === key ? (sortAsc ? " ▲" : " ▼") : "");

  return (
    <div className="space-y-6 p-4">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Maschinenauslastung</h1>
        <p className="mt-1 text-sm text-gray-600">
          Auslastung je Maschine auf Basis von Prozesszeiten, Jahresstückzahl und
          Maschinenverfügbarkeit (Jahresstunden).
        </p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Filter</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Werk *</span>
            <select
              className="mt-1 w-full rounded border border-gray-300 px-2 py-1.5"
              value={plantId ?? ""}
              onChange={(e) => {
                setPlantId(e.target.value ? Number(e.target.value) : null);
                setCustomerId(null);
                setProgramId(null);
                setSelectedProjectIds([]);
              }}
            >
              <option value="">– Werk wählen –</option>
              {werke.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.code})
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Kunde</span>
            <select
              className="mt-1 w-full rounded border border-gray-300 px-2 py-1.5"
              value={customerId ?? ""}
              disabled={plantId == null}
              onChange={(e) => {
                setCustomerId(e.target.value ? Number(e.target.value) : null);
                setProgramId(null);
                setSelectedProjectIds([]);
              }}
            >
              <option value="">– optional –</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Programm</span>
            <select
              className="mt-1 w-full rounded border border-gray-300 px-2 py-1.5"
              value={programId ?? ""}
              disabled={customerId == null}
              onChange={(e) => {
                setProgramId(e.target.value ? Number(e.target.value) : null);
                setSelectedProjectIds([]);
              }}
            >
              <option value="">– optional –</option>
              {programs.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <div className="text-sm">
            <span className="font-medium text-gray-700">Projekte (Mehrfachauswahl)</span>
            <div
              className="mt-1 max-h-32 overflow-y-auto rounded border border-gray-300 p-2"
              aria-disabled={programId == null}
            >
              {programId == null && (
                <p className="text-gray-500">Zuerst Programm wählen</p>
              )}
              {programId != null && projects.length === 0 && (
                <p className="text-gray-500">Keine Projekte</p>
              )}
              {projects.map((p) => (
                <label key={p.id} className="flex items-center gap-2 py-0.5">
                  <input
                    type="checkbox"
                    checked={selectedProjectIds.includes(p.id)}
                    onChange={() => toggleProject(p.id)}
                  />
                  <span>{p.name}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            disabled={plantId == null || busy}
            onClick={() => void load()}
          >
            {busy ? "Lädt…" : "Aktualisieren"}
          </button>
          {data?.no_projects_selected && (
            <span className="text-sm text-amber-700">Keine Projekte ausgewählt – Auslastung 0 %</span>
          )}
        </div>
      </section>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      {plantId == null && (
        <p className="text-sm text-gray-500">Bitte Werk auswählen, um Maschinen anzuzeigen.</p>
      )}

      {data && plantId != null && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="Maschinen gesamt" value={String(data.summary.machine_count)} />
            <KpiCard
              label="Durchschnittliche Auslastung"
              value={formatPercentOrDash(data.summary.average_utilization_pct)}
              hint={
                data.summary.plant_utilization_pct != null
                  ? `Werk gesamt: ${formatPercentOrDash(data.summary.plant_utilization_pct)}`
                  : undefined
              }
            />
            <KpiCard
              label="Maximal ausgelastete Maschine"
              value={formatPercentOrDash(data.summary.max_utilization_pct)}
              hint={data.summary.max_utilization_maschine_name ?? undefined}
              tone={
                data.summary.max_utilization_pct != null && data.summary.max_utilization_pct > 100
                  ? "warning"
                  : "neutral"
              }
            />
            <KpiCard
              label="Überlastete Maschinen"
              value={String(data.summary.overloaded_count)}
              tone={data.summary.overloaded_count > 0 ? "negative" : "positive"}
            />
          </div>

          <p className="text-xs text-gray-500">
            Planungsperiode: {data.planning_period.label} – {data.planning_period.basis}
          </p>

          <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-left text-gray-600">
                <tr>
                  <th className="cursor-pointer px-3 py-2" onClick={() => toggleSort("bezeichnung")}>
                    Maschine{sortIndicator("bezeichnung")}
                  </th>
                  <th className="px-3 py-2">Werk</th>
                  <th className="px-3 py-2">Maschinen-ID</th>
                  <th
                    className="cursor-pointer px-3 py-2 text-right"
                    onClick={() => toggleSort("available_hours")}
                  >
                    Verfügbare h{sortIndicator("available_hours")}
                  </th>
                  <th
                    className="cursor-pointer px-3 py-2 text-right"
                    onClick={() => toggleSort("required_hours")}
                  >
                    Benötigte h{sortIndicator("required_hours")}
                  </th>
                  <th
                    className="cursor-pointer px-3 py-2 text-right"
                    onClick={() => toggleSort("utilization_pct")}
                  >
                    Auslastung %{sortIndicator("utilization_pct")}
                  </th>
                  <th
                    className="cursor-pointer px-3 py-2 text-right"
                    onClick={() => toggleSort("rest_capacity_hours")}
                  >
                    Rest / Überlast{sortIndicator("rest_capacity_hours")}
                  </th>
                  <th className="px-3 py-2">Projekte</th>
                </tr>
              </thead>
              <tbody>
                {sortedMachines.map((row) => (
                  <tr
                    key={row.maschine_id}
                    className={`border-t border-gray-100 ${row.is_overloaded ? "bg-red-50" : ""}`}
                  >
                    <td className="px-3 py-2 font-medium">
                      {row.bezeichnung}
                      <div className="text-xs text-gray-500">{row.maschinen_nr}</div>
                    </td>
                    <td className="px-3 py-2">{row.werk_name ?? "–"}</td>
                    <td className="px-3 py-2">{row.maschine_id}</td>
                    <td className="px-3 py-2 text-right">{formatHours(row.available_hours)}</td>
                    <td className="px-3 py-2 text-right">
                      {row.has_demand ? formatHours(row.required_hours) : "kein Bedarf"}
                    </td>
                    <td
                      className={`px-3 py-2 text-right font-semibold ${
                        row.is_overloaded ? "text-red-700" : ""
                      }`}
                    >
                      {row.utilization_pct != null
                        ? formatPercentOrDash(row.utilization_pct)
                        : row.has_demand
                          ? "nicht berechenbar"
                          : formatPercentOrDash(0)}
                    </td>
                    <td
                      className={`px-3 py-2 text-right ${row.is_overloaded ? "text-red-700 font-medium" : ""}`}
                    >
                      {row.has_demand ? restLabel(row) : "–"}
                    </td>
                    <td className="px-3 py-2">
                      {row.projects.length === 0 ? (
                        <span className="text-gray-400">–</span>
                      ) : (
                        <ul className="list-inside list-disc text-xs">
                          {row.projects.map((p) => (
                            <li key={`${p.project_id}-${p.source_label}`}>
                              {p.project_name}: {p.source_label} ({formatHours(p.required_hours)} h)
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
