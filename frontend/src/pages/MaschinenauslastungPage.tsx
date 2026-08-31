import { useCallback, useEffect, useMemo, useState } from "react";

import { getMaschinenAuslastung } from "../api/maschinen";
import { listCustomers, listPrograms, listProjects } from "../api/hierarchy";
import { api } from "../api/client";
import type { Customer, Program, Project } from "../types/hierarchy";
import type {
  MaschineAuslastungResponse,
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
  const [selectedYear, setSelectedYear] = useState<number>(2026);
  const [machineFilter, setMachineFilter] = useState("");

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
    if (plantId != null) void load();
    else setData(null);
  }, [plantId, customerId, programId, selectedProjectIds, load]);

  const yearSummary = useMemo(
    () => (data ? summaryForYear(data, selectedYear) : null),
    [data, selectedYear],
  );

  const filteredYearRows = useMemo(() => {
    if (!data) return [];
    const term = machineFilter.trim().toLowerCase();
    let rows = data.yearly_rows.filter((r) => r.year === selectedYear);
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
  }, [data, selectedYear, machineFilter, sortKey, sortAsc]);

  const toggleSort = (key: YearSortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(key === "machine_name" || key === "year");
    }
  };

  const toggleProject = (id: number) => {
    setSelectedProjectIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
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
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
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
            <span className="font-medium text-gray-700">Projekte</span>
            <div className="mt-1 max-h-32 overflow-y-auto rounded border border-gray-300 p-2">
              {programId == null && <p className="text-gray-500">Zuerst Programm wählen</p>}
              {programId != null &&
                projects.map((p) => (
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
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Jahr (KPIs)</span>
            <select
              className="mt-1 w-full rounded border border-gray-300 px-2 py-1.5"
              value={selectedYear}
              onChange={(e) => setSelectedYear(Number(e.target.value))}
            >
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

      {data && plantId != null && yearSummary && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label={`Maschinen gesamt (${selectedYear})`}
              value={String(yearSummary.machineCount)}
            />
            <KpiCard
              label={`Ø Auslastung ${selectedYear}`}
              value={formatPercentOrDash(yearSummary.average)}
            />
            <KpiCard
              label={`Max. Auslastung ${selectedYear}`}
              value={formatPercentOrDash(yearSummary.maxPct)}
              hint={yearSummary.maxName ?? undefined}
              tone={
                yearSummary.maxPct != null && yearSummary.maxPct > 100 ? "warning" : "neutral"
              }
            />
            <KpiCard
              label={`Überlastungen ${selectedYear}`}
              value={String(yearSummary.overloaded)}
              tone={yearSummary.overloaded > 0 ? "negative" : "positive"}
            />
          </div>

          <p className="text-xs text-gray-500">
            {data.planning_period.label}: {data.planning_period.basis}
            {data.planning_period.oee_in_available_hours &&
              " · OEE ist in den verfügbaren Stunden enthalten (nicht doppelt angewendet)."}
          </p>

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
                      {row.utilization_pct != null
                        ? formatPercentOrDash(row.utilization_pct)
                        : row.has_demand
                          ? "nicht berechenbar"
                          : formatPercentOrDash(0)}
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
        </>
      )}
    </div>
  );
}
