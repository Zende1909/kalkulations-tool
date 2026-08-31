import { useCallback, useEffect, useMemo, useState } from "react";

import { getMaschinenAuslastung } from "../api/maschinen";
import { listCustomers, listPrograms, listProjects, getProject } from "../api/hierarchy";
import { api } from "../api/client";
import type { Customer, Program, Project } from "../types/hierarchy";
import { PROJECT_STATUSES } from "../types/hierarchy";
import type {
  MaschineAuslastungResponse,
  MaschineAuslastungRow,
  MaschineAuslastungYearRow,
} from "../types/maschineAuslastung";
import { UTILIZATION_YEARS } from "../types/maschineAuslastung";
import type { Werk } from "../types/stammdaten";
import { formatPercentOrDash } from "./businessCaseFormatting";

type YearSortKey =
  | "year"
  | "machine_name"
  | "run_hours"
  | "setup_hours"
  | "required_hours"
  | "utilization_pct";

type YearSelection = number | "all";

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

function formatOee(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return `${(value * 100).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %`;
}

function restLabel(row: MaschineAuslastungYearRow): string {
  if (row.is_overloaded && row.overload_hours != null) {
    return `Überlastung ${formatHours(row.overload_hours)} h`;
  }
  if (row.remaining_hours != null) {
    return `${formatHours(row.remaining_hours)} h`;
  }
  return "–";
}

function utilizationCell(row: MaschineAuslastungYearRow | undefined): string {
  if (row == null) return formatPercentOrDash(0);
  if (row.utilization_pct != null) return formatPercentOrDash(row.utilization_pct);
  if (row.has_demand) return "nicht berechenbar";
  return formatPercentOrDash(0);
}

function machineHasUtilization(machine: MaschineAuslastungRow): boolean {
  return machine.has_demand || machine.yearly_breakdown.some((y) => y.has_demand || y.required_hours > 0);
}

function yearRowHasUtilization(row: MaschineAuslastungYearRow): boolean {
  return row.has_demand || row.required_hours > 0;
}

function aggregateUtilizationPct(totalRequired: number, totalAvailable: number): number | null {
  if (totalAvailable <= 0) return totalRequired > 0 ? null : 0;
  return (totalRequired / totalAvailable) * 100;
}

function summaryForYear(data: MaschineAuslastungResponse, year: number) {
  const rows = data.yearly_rows.filter((r) => r.year === year);
  const utilPcts = rows
    .filter((r) => r.utilization_pct != null && r.has_demand)
    .map((r) => r.utilization_pct as number);
  const overloaded = rows.filter((r) => r.is_overloaded).length;
  const maxRow = rows.reduce<MaschineAuslastungYearRow | null>((best, row) => {
    if (row.utilization_pct == null) return best;
    if (best == null || row.utilization_pct > (best.utilization_pct ?? -1)) return row;
    return best;
  }, null);
  return {
    average: utilPcts.length
      ? utilPcts.reduce((a, b) => a + b, 0) / utilPcts.length
      : null,
    maxPct: maxRow?.utilization_pct ?? null,
    maxName: maxRow?.machine_name ?? null,
    overloaded,
    machineCount: data.summary.machine_count,
  };
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
  const [selectedProjectsById, setSelectedProjectsById] = useState<Record<number, Project>>({});
  const [projectStatusFilter, setProjectStatusFilter] = useState<string>("");
  const [selectedYear, setSelectedYear] = useState<YearSelection>("all");
  const [machineFilter, setMachineFilter] = useState("");
  const [showEmptyMachines, setShowEmptyMachines] = useState(false);

  const [data, setData] = useState<MaschineAuslastungResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<YearSortKey>("utilization_pct");
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
    listProjects({
      programId,
      active: true,
      status: projectStatusFilter || undefined,
    })
      .then(setProjects)
      .catch(() => setProjects([]));
  }, [programId, projectStatusFilter]);

  useEffect(() => {
    let cancelled = false;
    for (const id of selectedProjectIds) {
      getProject(id)
        .then((project) => {
          if (!cancelled) {
            setSelectedProjectsById((prev) => (prev[id] ? prev : { ...prev, [id]: project }));
          }
        })
        .catch(() => undefined);
    }
    return () => {
      cancelled = true;
    };
  }, [selectedProjectIds]);

  useEffect(() => {
    if (!projectStatusFilter) return;
    setSelectedProjectIds((prev) =>
      prev.filter((id) => {
        const project = selectedProjectsById[id];
        return project == null || project.status === projectStatusFilter;
      }),
    );
  }, [projectStatusFilter]);

  const load = useCallback(async () => {
    if (plantId == null) {
      setError("Bitte ein Werk auswählen.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const status = projectStatusFilter || undefined;
      const resp = await getMaschinenAuslastung(
        selectedProjectIds.length > 0
          ? {
              plant_id: plantId,
              project_ids: selectedProjectIds,
              project_status: status,
            }
          : {
              plant_id: plantId,
              customer_id: customerId ?? undefined,
              program_id: programId ?? undefined,
              project_status: status,
            },
      );
      setData(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laden fehlgeschlagen");
      setData(null);
    } finally {
      setBusy(false);
    }
  }, [plantId, customerId, programId, selectedProjectIds, projectStatusFilter]);

  useEffect(() => {
    if (plantId != null) void load();
    else setData(null);
  }, [plantId, customerId, programId, selectedProjectIds, projectStatusFilter, load]);

  const showAllYears = selectedYear === "all";

  const kpiSummary = useMemo(() => {
    if (!data) return null;
    if (showAllYears) {
      return {
        labelSuffix: "Alle Jahre",
        machineCount: data.summary.machine_count,
        average: data.summary.average_utilization_pct,
        maxPct: data.summary.max_utilization_pct,
        maxName: data.summary.max_utilization_maschine_name,
        overloaded: data.summary.overloaded_count,
      };
    }
    const yearStats = summaryForYear(data, selectedYear);
    return {
      labelSuffix: String(selectedYear),
      machineCount: yearStats.machineCount,
      average: yearStats.average,
      maxPct: yearStats.maxPct,
      maxName: yearStats.maxName,
      overloaded: yearStats.overloaded,
    };
  }, [data, selectedYear, showAllYears]);

  const matrixRows = useMemo(() => {
    if (!data || !showAllYears) return [];
    const term = machineFilter.trim().toLowerCase();
    let rows = [...data.machines];
    if (!showEmptyMachines) {
      rows = rows.filter(machineHasUtilization);
    }
    if (term) {
      rows = rows.filter(
        (m) =>
          m.bezeichnung.toLowerCase().includes(term) ||
          m.maschinen_nr.toLowerCase().includes(term) ||
          String(m.maschine_id).includes(term),
      );
    }
    rows.sort((a, b) => a.bezeichnung.localeCompare(b.bezeichnung, "de"));
    return rows;
  }, [data, showAllYears, machineFilter, showEmptyMachines]);

  const aggregateMatrixByYear = useMemo(() => {
    if (!showAllYears || matrixRows.length === 0) return [];
    return UTILIZATION_YEARS.map((year) => {
      let totalRequired = 0;
      let totalAvailable = 0;
      for (const machine of matrixRows) {
        const yearRow = machine.yearly_breakdown.find((y) => y.year === year);
        if (yearRow == null) continue;
        totalRequired += yearRow.required_hours;
        totalAvailable += yearRow.available_hours ?? 0;
      }
      const pct = aggregateUtilizationPct(totalRequired, totalAvailable);
      return {
        year,
        totalRequired,
        totalAvailable,
        pct,
        isOverloaded: totalAvailable > 0 && totalRequired > totalAvailable,
      };
    });
  }, [matrixRows, showAllYears]);

  const filteredYearRows = useMemo(() => {
    if (!data || showAllYears) return [];
    const term = machineFilter.trim().toLowerCase();
    let rows = data.yearly_rows.filter((r) => r.year === selectedYear);
    if (!showEmptyMachines) {
      rows = rows.filter(yearRowHasUtilization);
    }
    if (term) {
      rows = rows.filter(
        (r) =>
          r.machine_name.toLowerCase().includes(term) ||
          r.maschinen_nr.toLowerCase().includes(term) ||
          String(r.machine_id).includes(term),
      );
    }
    rows = [...rows];
    rows.sort((a, b) => {
      const av = a[sortKey === "machine_name" ? "machine_name" : sortKey];
      const bv = b[sortKey === "machine_name" ? "machine_name" : sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string" && typeof bv === "string") {
        return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortAsc ? Number(av) - Number(bv) : Number(bv) - Number(av);
    });
    return rows;
  }, [data, selectedYear, showAllYears, machineFilter, sortKey, sortAsc, showEmptyMachines]);

  const aggregateSingleYear = useMemo(() => {
    if (showAllYears || filteredYearRows.length === 0) return null;
    const totalRequired = filteredYearRows.reduce((sum, row) => sum + row.required_hours, 0);
    const totalRun = filteredYearRows.reduce((sum, row) => sum + row.run_hours, 0);
    const totalSetup = filteredYearRows.reduce((sum, row) => sum + row.setup_hours, 0);
    const totalAvailable = filteredYearRows.reduce((sum, row) => sum + (row.available_hours ?? 0), 0);
    const pct = aggregateUtilizationPct(totalRequired, totalAvailable);
    return {
      totalRequired,
      totalRun,
      totalSetup,
      totalAvailable,
      pct,
      isOverloaded: totalAvailable > 0 && totalRequired > totalAvailable,
    };
  }, [filteredYearRows, showAllYears]);

  const toggleSort = (key: YearSortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(key === "machine_name" || key === "year");
    }
  };

  const toggleProject = (project: Project) => {
    setSelectedProjectsById((prev) => ({ ...prev, [project.id]: project }));
    setSelectedProjectIds((prev) =>
      prev.includes(project.id) ? prev.filter((x) => x !== project.id) : [...prev, project.id],
    );
  };

  const removeSelectedProject = (id: number) => {
    setSelectedProjectIds((prev) => prev.filter((x) => x !== id));
  };

  const sortIndicator = (key: YearSortKey) => (sortKey === key ? (sortAsc ? " ▲" : " ▼") : "");

  return (
    <div className="space-y-6 p-4">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Maschinenauslastung</h1>
        <p className="mt-1 text-sm text-gray-600">
          Jahresauslastung 2026–2040: Laufzeit + Rüstzeit vs. verfügbare Stunden (Brutto × OEE).
          Veredelung wird nicht berücksichtigt.
        </p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Filter</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6">
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
                setSelectedProjectsById({});
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
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Projektstatus</span>
            <select
              className="mt-1 w-full rounded border border-gray-300 px-2 py-1.5"
              value={projectStatusFilter}
              disabled={plantId == null}
              onChange={(e) => setProjectStatusFilter(e.target.value)}
            >
              <option value="">– alle –</option>
              {PROJECT_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>
          <div className="text-sm lg:col-span-2">
            <span className="font-medium text-gray-700">Projekte hinzufügen</span>
            <div className="mt-1 max-h-32 overflow-y-auto rounded border border-gray-300 p-2">
              {programId == null && <p className="text-gray-500">Zuerst Programm wählen</p>}
              {programId != null && projects.length === 0 && (
                <p className="text-gray-500">Keine Projekte für den Filter</p>
              )}
              {programId != null &&
                projects.map((p) => (
                  <label key={p.id} className="flex items-center gap-2 py-0.5">
                    <input
                      type="checkbox"
                      checked={selectedProjectIds.includes(p.id)}
                      onChange={() => toggleProject(p)}
                    />
                    <span>
                      {p.name}
                      <span className="text-xs text-gray-500"> ({p.status})</span>
                    </span>
                  </label>
                ))}
            </div>
          </div>
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Jahr</span>
            <select
              className="mt-1 w-full rounded border border-gray-300 px-2 py-1.5"
              value={selectedYear === "all" ? "all" : String(selectedYear)}
              onChange={(e) => {
                const value = e.target.value;
                setSelectedYear(value === "all" ? "all" : Number(value));
              }}
            >
              <option value="all">Alle Jahre</option>
              {UTILIZATION_YEARS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            disabled={plantId == null || busy}
            onClick={() => void load()}
          >
            {busy ? "Lädt…" : "Aktualisieren"}
          </button>
          <input
            type="search"
            placeholder="Maschine filtern…"
            className="rounded border border-gray-300 px-2 py-1.5 text-sm"
            value={machineFilter}
            onChange={(e) => setMachineFilter(e.target.value)}
          />
          <button
            type="button"
            className={`rounded border px-3 py-1.5 text-sm ${
              showEmptyMachines
                ? "border-slate-800 bg-slate-800 text-white"
                : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
            }`}
            onClick={() => setShowEmptyMachines((value) => !value)}
          >
            Leere anzeigen
          </button>
          {data?.uses_all_matching_projects && (
            <span className="text-sm text-blue-700">
              Alle passenden Projekte einbezogen ({data.resolved_project_ids.length})
            </span>
          )}
          {selectedProjectIds.length > 0 && (
            <span className="text-sm text-gray-600">
              {selectedProjectIds.length} Projekt(e) manuell ausgewählt
            </span>
          )}
        </div>
        {selectedProjectIds.length > 0 && (
          <div className="mt-3 rounded border border-gray-200 bg-gray-50 p-2 text-sm">
            <div className="mb-1 font-medium text-gray-700">Ausgewählte Projekte (über alle Kunden)</div>
            <div className="flex flex-wrap gap-2">
              {selectedProjectIds.map((id) => {
                const project = selectedProjectsById[id];
                return (
                  <button
                    key={id}
                    type="button"
                    className="rounded border border-gray-300 bg-white px-2 py-1 text-xs hover:bg-gray-100"
                    onClick={() => removeSelectedProject(id)}
                    title="Aus Auswahl entfernen"
                  >
                    {project?.name ?? `Projekt ${id}`} ×
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </section>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      {plantId == null && (
        <p className="text-sm text-gray-500">Bitte Werk auswählen, um Maschinen anzuzeigen.</p>
      )}

      {data && plantId != null && kpiSummary && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label={`Maschinen gesamt (${kpiSummary.labelSuffix})`}
              value={String(kpiSummary.machineCount)}
            />
            <KpiCard
              label={`Ø Auslastung ${kpiSummary.labelSuffix}`}
              value={formatPercentOrDash(kpiSummary.average)}
            />
            <KpiCard
              label={`Max. Auslastung ${kpiSummary.labelSuffix}`}
              value={formatPercentOrDash(kpiSummary.maxPct)}
              hint={kpiSummary.maxName ?? undefined}
              tone={
                kpiSummary.maxPct != null && kpiSummary.maxPct > 100 ? "warning" : "neutral"
              }
            />
            <KpiCard
              label={`Überlastungen ${kpiSummary.labelSuffix}`}
              value={String(kpiSummary.overloaded)}
              tone={kpiSummary.overloaded > 0 ? "negative" : "positive"}
            />
          </div>

          <p className="text-xs text-gray-500">
            {data.planning_period.label}: {data.planning_period.basis}
            {data.planning_period.oee_in_available_hours &&
              " · OEE ist in den verfügbaren Stunden enthalten (nicht doppelt angewendet)."}
          </p>

          {showAllYears ? (
            <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-left text-gray-600">
                  <tr>
                    <th className="sticky left-0 z-10 bg-gray-50 px-3 py-2">Maschine</th>
                    <th className="px-3 py-2 text-right whitespace-nowrap">Verfügbar h</th>
                    {UTILIZATION_YEARS.map((year) => (
                      <th key={year} className="px-3 py-2 text-right whitespace-nowrap">
                        {year}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {aggregateMatrixByYear.length > 0 && (
                    <tr className="border-b-2 border-slate-200 bg-slate-50 font-semibold">
                      <td className="sticky left-0 z-10 bg-slate-50 px-3 py-2">Gesamtauslastung</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        {formatHours(matrixRows.reduce((sum, machine) => sum + (machine.available_hours ?? 0), 0))}
                      </td>
                      {aggregateMatrixByYear.map((row) => (
                        <td
                          key={row.year}
                          className={`px-3 py-2 text-right whitespace-nowrap ${row.isOverloaded ? "bg-red-100 text-red-700" : ""}`}
                        >
                          {formatPercentOrDash(row.pct)}
                        </td>
                      ))}
                    </tr>
                  )}
                  {matrixRows.map((machine) => (
                    <tr key={machine.maschine_id} className="border-t border-gray-100">
                      <td className="sticky left-0 z-10 bg-white px-3 py-2 font-medium">
                        {machine.bezeichnung}
                        <div className="text-xs text-gray-500">
                          ID {machine.maschine_id} · {machine.maschinen_nr}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        {formatHours(machine.available_hours)}
                      </td>
                      {UTILIZATION_YEARS.map((year) => {
                        const yearRow = machine.yearly_breakdown.find((y) => y.year === year);
                        const overloaded = yearRow?.is_overloaded ?? false;
                        return (
                          <td
                            key={year}
                            className={`px-3 py-2 text-right whitespace-nowrap ${overloaded ? "bg-red-50 font-semibold text-red-700" : ""}`}
                          >
                            {utilizationCell(yearRow)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-left text-gray-600">
                  <tr>
                    <th className="cursor-pointer px-3 py-2" onClick={() => toggleSort("year")}>
                      Jahr{sortIndicator("year")}
                    </th>
                    <th className="cursor-pointer px-3 py-2" onClick={() => toggleSort("machine_name")}>
                      Maschine{sortIndicator("machine_name")}
                    </th>
                    <th className="px-3 py-2 text-right">Brutto h</th>
                    <th className="px-3 py-2 text-right">OEE</th>
                    <th className="px-3 py-2 text-right">Verfügbar h</th>
                    <th className="cursor-pointer px-3 py-2 text-right" onClick={() => toggleSort("run_hours")}>
                      Laufzeit{sortIndicator("run_hours")}
                    </th>
                    <th className="cursor-pointer px-3 py-2 text-right" onClick={() => toggleSort("setup_hours")}>
                      Rüstzeit{sortIndicator("setup_hours")}
                    </th>
                    <th
                      className="cursor-pointer px-3 py-2 text-right"
                      onClick={() => toggleSort("required_hours")}
                    >
                      Gesamtbedarf{sortIndicator("required_hours")}
                    </th>
                    <th
                      className="cursor-pointer px-3 py-2 text-right"
                      onClick={() => toggleSort("utilization_pct")}
                    >
                      Auslastung %{sortIndicator("utilization_pct")}
                    </th>
                    <th className="px-3 py-2 text-right">Rest / Überlast</th>
                    <th className="px-3 py-2">Projekte</th>
                  </tr>
                </thead>
                <tbody>
                  {aggregateSingleYear && (
                    <tr className="border-b-2 border-slate-200 bg-slate-50 font-semibold">
                      <td className="px-3 py-2">{selectedYear}</td>
                      <td className="px-3 py-2">Gesamtauslastung</td>
                      <td className="px-3 py-2 text-right">–</td>
                      <td className="px-3 py-2 text-right">–</td>
                      <td className="px-3 py-2 text-right">{formatHours(aggregateSingleYear.totalAvailable)}</td>
                      <td className="px-3 py-2 text-right">{formatHours(aggregateSingleYear.totalRun)}</td>
                      <td className="px-3 py-2 text-right">{formatHours(aggregateSingleYear.totalSetup)}</td>
                      <td className="px-3 py-2 text-right">{formatHours(aggregateSingleYear.totalRequired)}</td>
                      <td
                        className={`px-3 py-2 text-right ${aggregateSingleYear.isOverloaded ? "text-red-700" : ""}`}
                      >
                        {formatPercentOrDash(aggregateSingleYear.pct)}
                      </td>
                      <td
                        className={`px-3 py-2 text-right ${aggregateSingleYear.isOverloaded ? "text-red-700" : ""}`}
                      >
                        {aggregateSingleYear.isOverloaded
                          ? `Überlastung ${formatHours(aggregateSingleYear.totalRequired - aggregateSingleYear.totalAvailable)} h`
                          : formatHours(aggregateSingleYear.totalAvailable - aggregateSingleYear.totalRequired)}
                      </td>
                      <td className="px-3 py-2">–</td>
                    </tr>
                  )}
                  {filteredYearRows.map((row) => (
                    <tr
                      key={`${row.machine_id}-${row.year}`}
                      className={`border-t border-gray-100 ${row.is_overloaded ? "bg-red-50" : ""}`}
                    >
                      <td className="px-3 py-2">{row.year}</td>
                      <td className="px-3 py-2 font-medium">
                        {row.machine_name}
                        <div className="text-xs text-gray-500">ID {row.machine_id} · {row.maschinen_nr}</div>
                      </td>
                      <td className="px-3 py-2 text-right">{formatHours(row.gross_hours)}</td>
                      <td className="px-3 py-2 text-right">{formatOee(row.oee)}</td>
                      <td className="px-3 py-2 text-right">{formatHours(row.available_hours)}</td>
                      <td className="px-3 py-2 text-right">
                        {row.has_demand ? formatHours(row.run_hours) : "kein Bedarf"}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {row.setup_hours > 0 ? formatHours(row.setup_hours) : row.has_demand ? "0,00" : "–"}
                      </td>
                      <td className="px-3 py-2 text-right">{formatHours(row.required_hours)}</td>
                      <td
                        className={`px-3 py-2 text-right font-semibold ${row.is_overloaded ? "text-red-700" : ""}`}
                      >
                        {utilizationCell(row)}
                      </td>
                      <td className={`px-3 py-2 text-right ${row.is_overloaded ? "text-red-700" : ""}`}>
                        {row.has_demand ? restLabel(row) : "–"}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {row.project_ids.length === 0 ? (
                          "–"
                        ) : (
                          <span>{row.project_ids.join(", ")}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {!showAllYears && (
          <details className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <summary className="cursor-pointer font-medium text-gray-800">
              Maschinenübersicht (Jahresdetails je Maschine)
            </summary>
            <div className="mt-4 space-y-4">
              {data.machines.map((m) => (
                <div key={m.maschine_id} className="border-t border-gray-100 pt-3">
                  <div className="font-medium">
                    {m.bezeichnung} ({m.maschinen_nr}) · Brutto {formatHours(m.gross_hours)} h · OEE{" "}
                    {formatOee(m.oee)} · Verfügbar {formatHours(m.available_hours)} h/Jahr
                  </div>
                  <div className="mt-2 overflow-x-auto">
                    <table className="min-w-full text-xs">
                      <thead>
                        <tr className="text-gray-500">
                          <th className="py-1 pr-2 text-left">Jahr</th>
                          <th className="py-1 pr-2 text-right">Laufzeit</th>
                          <th className="py-1 pr-2 text-right">Rüstzeit</th>
                          <th className="py-1 pr-2 text-right">Gesamt</th>
                          <th className="py-1 text-right">Auslastung</th>
                        </tr>
                      </thead>
                      <tbody>
                        {m.yearly_breakdown
                          .filter((y) => y.has_demand)
                          .map((y) => (
                            <tr key={y.year} className={y.is_overloaded ? "text-red-700" : ""}>
                              <td className="py-1 pr-2">{y.year}</td>
                              <td className="py-1 pr-2 text-right">{formatHours(y.run_hours)}</td>
                              <td className="py-1 pr-2 text-right">{formatHours(y.setup_hours)}</td>
                              <td className="py-1 pr-2 text-right">{formatHours(y.required_hours)}</td>
                              <td className="py-1 text-right">{formatPercentOrDash(y.utilization_pct)}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          </details>
          )}
        </>
      )}
    </div>
  );
}
