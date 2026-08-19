import { useCallback, useEffect, useState } from "react";

import { getAssemblyOverview, getDashboardSummary } from "../api/dashboard";
import {
  baugruppePdfUrl,
  baugruppeXlsxUrl,
  dashboardPdfUrl,
  dashboardXlsxUrl,
  downloadReport,
} from "../api/reports";
import { ExportButtons } from "../components/ExportButtons";
import type {
  AssemblyOverview,
  ChartBarItem,
  DashboardQuery,
  DashboardSummary,
} from "../types/dashboard";

function euro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "Keine Daten";
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function int(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "0";
  return value.toLocaleString("de-DE");
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "–";
  try {
    return new Date(value).toLocaleString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

function formatDay(value: string | null | undefined): string {
  if (!value) return "–";
  try {
    return new Date(value).toLocaleDateString("de-DE");
  } catch {
    return value;
  }
}

function chartHasValues(items: ChartBarItem[] | Array<{ label: string; value: number }>): boolean {
  return items.some((item) => item.value !== 0);
}

const KPI_CARDS: Array<{
  key: keyof DashboardSummary["kpis"];
  label: string;
  format: "int" | "euro" | "avg";
}> = [
  { key: "anzahl_projekte", label: "Anzahl Projekte", format: "int" },
  { key: "anzahl_spritzguss_kalkulationen", label: "Einzelteil-Kalkulationen", format: "int" },
  { key: "anzahl_baugruppen", label: "Anzahl Baugruppen", format: "int" },
  { key: "investitionen_gesamt", label: "Gesamtinvestitionsvolumen", format: "euro" },
  { key: "umsatzpotenzial_jahr", label: "Summe Jahresumsätze", format: "euro" },
  { key: "durchschnitt_preis_pro_stueck", label: "Ø Preis pro Stück", format: "avg" },
  { key: "durchschnitt_endpreis_einzelteil", label: "Ø Endpreis je Einzelteil", format: "avg" },
  { key: "durchschnitt_baugruppenpreis", label: "Ø Baugruppenpreis je Stück", format: "avg" },
];

function HorizontalBarChart({
  items,
  unit = "€",
}: {
  items: Array<{ label: string; value: number }>;
  unit?: string;
}) {
  if (!chartHasValues(items)) {
    return <p className="text-sm text-gray-500">Keine Diagrammdaten für die aktuelle Auswahl.</p>;
  }
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.label}>
          <div className="mb-1 flex justify-between gap-2 text-sm">
            <span className="truncate text-gray-700" title={item.label}>
              {item.label}
            </span>
            <span className="shrink-0 tabular-nums font-medium">
              {item.value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}{" "}
              {unit}
            </span>
          </div>
          <div className="h-3 overflow-hidden rounded bg-gray-100">
            <div
              className="h-3 rounded bg-slate-600"
              style={{ width: `${Math.max((item.value / max) * 100, 2)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function VerticalBarChart({
  items,
  unit = "€",
}: {
  items: Array<{ label: string; value: number }>;
  unit?: string;
}) {
  if (!chartHasValues(items)) {
    return <p className="text-sm text-gray-500">Keine Diagrammdaten für die aktuelle Auswahl.</p>;
  }
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="flex items-end gap-2 overflow-x-auto pb-2 pt-4" style={{ minHeight: 180 }}>
      {items.map((item) => (
        <div key={item.label} className="flex min-w-[72px] flex-1 flex-col items-center gap-1">
          <span className="text-xs tabular-nums text-gray-600">
            {item.value.toLocaleString("de-DE", { maximumFractionDigits: 0 })} {unit}
          </span>
          <div
            className="w-full max-w-[48px] rounded-t bg-emerald-600"
            style={{ height: `${Math.max((item.value / max) * 120, 4)}px` }}
            title={`${item.label}: ${item.value}`}
          />
          <span className="max-w-[72px] truncate text-center text-xs text-gray-500" title={item.label}>
            {item.label}
          </span>
        </div>
      ))}
    </div>
  );
}

const EMPTY_FILTERS: DashboardQuery = {};

export function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [projectFilter, setProjectFilter] = useState("");
  const [customerFilter, setCustomerFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [kalkulationsart, setKalkulationsart] = useState("");
  const [applied, setApplied] = useState<DashboardQuery>(EMPTY_FILTERS);
  const [loading, setLoading] = useState(true);
  const [exportBusy, setExportBusy] = useState(false);
  const [rowExportId, setRowExportId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<AssemblyOverview | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async (filters: DashboardQuery) => {
    setLoading(true);
    setError(null);
    try {
      const summary = await getDashboardSummary(filters);
      setData(summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dashboard konnte nicht geladen werden");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(applied).catch(() => undefined);
  }, [load, applied]);

  const applyFilters = () => {
    setApplied({
      project: projectFilter || undefined,
      customer: customerFilter || undefined,
      status: statusFilter || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      kalkulationsart: kalkulationsart || undefined,
    });
  };

  const resetFilters = () => {
    setProjectFilter("");
    setCustomerFilter("");
    setStatusFilter("");
    setDateFrom("");
    setDateTo("");
    setKalkulationsart("");
    setApplied(EMPTY_FILTERS);
    setDetail(null);
  };

  const handleDashboardExport = async (format: "pdf" | "xlsx") => {
    setExportBusy(true);
    setError(null);
    try {
      const projectPart = applied.project?.replace(/[^\w\-]+/g, "_") || "gesamt";
      const filename = `dashboard_${projectPart}.${format === "pdf" ? "pdf" : "xlsx"}`;
      const path = format === "pdf" ? dashboardPdfUrl(applied) : dashboardXlsxUrl(applied);
      await downloadReport(path, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export fehlgeschlagen");
    } finally {
      setExportBusy(false);
    }
  };

  const handleAssemblyExport = async (assemblyId: number, format: "pdf" | "xlsx") => {
    setRowExportId(assemblyId);
    setError(null);
    try {
      const filename = `baugruppe_${assemblyId}.${format === "pdf" ? "pdf" : "xlsx"}`;
      const path = format === "pdf" ? baugruppePdfUrl(assemblyId) : baugruppeXlsxUrl(assemblyId);
      await downloadReport(path, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export fehlgeschlagen");
    } finally {
      setRowExportId(null);
    }
  };

  const openDetail = async (assemblyId: number) => {
    setDetailLoading(true);
    setError(null);
    try {
      setDetail(await getAssemblyOverview(assemblyId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Baugruppendetail konnte nicht geladen werden");
    } finally {
      setDetailLoading(false);
    }
  };

  const formatKpi = (key: keyof DashboardSummary["kpis"], format: "int" | "euro" | "avg") => {
    if (!data) return format === "avg" ? "Keine Daten" : "0";
    const value = data.kpis[key];
    if (format === "avg") return euro(value as number | null);
    if (format === "euro") return euro(value as number);
    return int(value as number);
  };

  const costChart = detail?.cost_structure?.length ? detail.cost_structure : (data?.cost_structure ?? []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
          <p className="mt-1 text-sm text-gray-600">
            Gesamtübersicht für Projekte, Kalkulationen, Baugruppen und Investitionen
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={loading}
            onClick={() => load(applied)}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            Aktualisieren
          </button>
          <ExportButtons
            busy={exportBusy}
            disabled={loading}
            onPdf={() => handleDashboardExport("pdf")}
            onExcel={() => handleDashboardExport("xlsx")}
          />
        </div>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-900">Filter</h3>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block text-sm">
            <span className="text-gray-600">Kunde</span>
            <select
              className="mt-1 block min-w-[180px] rounded border px-2 py-1.5"
              value={customerFilter}
              onChange={(e) => setCustomerFilter(e.target.value)}
            >
              <option value="">Alle Kunden</option>
              {(data?.filter_options.kunden ?? []).map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Projekt</span>
            <select
              className="mt-1 block min-w-[180px] rounded border px-2 py-1.5"
              value={projectFilter}
              onChange={(e) => setProjectFilter(e.target.value)}
            >
              <option value="">Alle Projekte</option>
              {(data?.filter_options.projekte ?? []).map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Status</span>
            <select
              className="mt-1 block min-w-[160px] rounded border px-2 py-1.5"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">Alle Status</option>
              {(data?.filter_options.statusse ?? []).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Kalkulationsart</span>
            <select
              className="mt-1 block min-w-[160px] rounded border px-2 py-1.5"
              value={kalkulationsart}
              onChange={(e) => setKalkulationsart(e.target.value)}
            >
              <option value="">Alle Arten</option>
              {(data?.filter_options.kalkulationsarten ?? ["Spritzguss", "Baugruppe"]).map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Zeitraum von</span>
            <input
              type="date"
              className="mt-1 block rounded border px-2 py-1.5"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Zeitraum bis</span>
            <input
              type="date"
              className="mt-1 block rounded border px-2 py-1.5"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </label>
          <button
            type="button"
            onClick={applyFilters}
            className="rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600"
          >
            Filter anwenden
          </button>
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50"
          >
            Filter zurücksetzen
          </button>
        </div>
      </section>

      {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-500">
          Dashboard wird geladen …
        </div>
      ) : data && !data.has_data ? (
        <section className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center">
          <h3 className="text-lg font-semibold text-gray-900">Keine Daten gefunden</h3>
          <p className="mx-auto mt-2 max-w-xl text-sm text-gray-600">
            {data.empty_message ||
              "Keine Daten für die gewählten Filter. Setzen Sie die Filter zurück oder legen Sie Projekte, Kalkulationen oder Investitionen an."}
          </p>
          <button
            type="button"
            onClick={resetFilters}
            className="mt-4 rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600"
          >
            Filter zurücksetzen
          </button>
        </section>
      ) : data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {KPI_CARDS.map(({ key, label, format }) => (
              <div key={key} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
                <p className="mt-2 text-2xl font-bold tabular-nums text-gray-900">{formatKpi(key, format)}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-4 font-semibold text-gray-900">
                Kostenstruktur {detail ? `– ${detail.name}` : "der Baugruppen"}
              </h3>
              <HorizontalBarChart items={costChart} />
            </section>
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-4 font-semibold text-gray-900">Vergleich Preis pro Stück</h3>
              <HorizontalBarChart
                items={data.price_comparison.map((i) => ({
                  label: `${i.label} (${i.typ})`,
                  value: i.value,
                }))}
              />
            </section>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-4 font-semibold text-gray-900">Jahresumsatz je Projekt</h3>
              <VerticalBarChart
                items={data.revenue_by_project.map((i) => ({
                  label: i.projekt,
                  value: i.betrag,
                }))}
              />
            </section>
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-4 font-semibold text-gray-900">Investitionsvolumen je Projekt</h3>
              <VerticalBarChart
                items={data.investment_by_project.map((i) => ({
                  label: i.projekt,
                  value: i.betrag,
                }))}
              />
            </section>
          </div>

          <section className="overflow-x-auto rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-4 font-semibold text-gray-900">Zuletzt geänderte Kalkulationen</h3>
            {data.recent_calculations.length === 0 ? (
              <p className="text-sm text-gray-500">Keine Kalkulationen in der aktuellen Auswahl.</p>
            ) : (
              <table className="w-full min-w-[800px] text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="py-2 pr-3">Art</th>
                    <th className="py-2 pr-3">Bezeichnung</th>
                    <th className="py-2 pr-3">Nummer</th>
                    <th className="py-2 pr-3">Kunde</th>
                    <th className="py-2 pr-3">Projekt</th>
                    <th className="py-2 pr-3 text-right">Preis/St.</th>
                    <th className="py-2">Geändert</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_calculations.map((row) => (
                    <tr key={`${row.kalkulationsart}-${row.id}`} className="border-b border-gray-100">
                      <td className="py-2 pr-3">{row.kalkulationsart}</td>
                      <td className="py-2 pr-3">{row.bezeichnung}</td>
                      <td className="py-2 pr-3">{row.nummer}</td>
                      <td className="py-2 pr-3">{row.kunde || "–"}</td>
                      <td className="py-2 pr-3">{row.projekt || "–"}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{euro(row.endpreis_je_stueck)}</td>
                      <td className="py-2 whitespace-nowrap">{formatDate(row.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="overflow-x-auto rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-4 font-semibold text-gray-900">Zuletzt angelegte Investitionen</h3>
            {data.recent_investments.length === 0 ? (
              <p className="text-sm text-gray-500">Keine Investitionen in der aktuellen Auswahl.</p>
            ) : (
              <table className="w-full min-w-[700px] text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="py-2 pr-3">Bezeichnung</th>
                    <th className="py-2 pr-3">Typ</th>
                    <th className="py-2 pr-3">Projekt</th>
                    <th className="py-2 pr-3 text-right">Betrag</th>
                    <th className="py-2">Angelegt</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_investments.map((row) => (
                    <tr key={row.id} className="border-b border-gray-100">
                      <td className="py-2 pr-3">{row.bezeichnung}</td>
                      <td className="py-2 pr-3">{row.typ}</td>
                      <td className="py-2 pr-3">{row.projekt || "–"}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{euro(row.betrag)}</td>
                      <td className="py-2 whitespace-nowrap">{formatDate(row.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="overflow-x-auto rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-4 font-semibold text-gray-900">Baugruppenübersicht</h3>
            {data.assemblies.length === 0 ? (
              <p className="text-sm text-gray-500">
                Keine Baugruppen gefunden. Legen Sie eine Baugruppe an oder setzen Sie die Filter zurück.
              </p>
            ) : (
              <table className="w-full min-w-[980px] text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="py-2 pr-3">Baugruppe</th>
                    <th className="py-2 pr-3">Projekt</th>
                    <th className="py-2 pr-3">Kunde</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3 text-right">Jahresstückzahl</th>
                    <th className="py-2 pr-3 text-right">Preis/St.</th>
                    <th className="py-2 pr-3 text-right">Jahresumsatz</th>
                    <th className="py-2 pr-3">Letzte Kalkulation</th>
                    <th className="py-2">Export</th>
                  </tr>
                </thead>
                <tbody>
                  {data.assemblies.map((row) => (
                    <tr
                      key={row.id}
                      className={`border-b border-gray-100 ${detail?.id === row.id ? "bg-slate-50" : ""}`}
                    >
                      <td className="py-2 pr-3">
                        <button
                          type="button"
                          className="text-left font-medium text-slate-800 underline-offset-2 hover:underline"
                          onClick={() => openDetail(row.id)}
                        >
                          {row.name}
                        </button>
                      </td>
                      <td className="py-2 pr-3">{row.projekt || "–"}</td>
                      <td className="py-2 pr-3">{row.kunde || "–"}</td>
                      <td className="py-2 pr-3">{row.status || "–"}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{int(row.jahresstueckzahl)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{euro(row.preis_je_stueck)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{euro(row.jahresumsatz)}</td>
                      <td className="py-2 pr-3 whitespace-nowrap">{formatDate(row.letzte_kalkulation)}</td>
                      <td className="py-2">
                        <div className="flex gap-1">
                          <ExportButtons
                            compact
                            busy={rowExportId === row.id}
                            onPdf={() => handleAssemblyExport(row.id, "pdf")}
                            onExcel={() => handleAssemblyExport(row.id, "xlsx")}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {(detail || detailLoading) && (
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <h3 className="font-semibold text-gray-900">
                    Baugruppendetail{detail ? ` – ${detail.name}` : ""}
                  </h3>
                  {detail && (
                    <p className="mt-1 text-sm text-gray-600">
                      {detail.kunde || "–"} · {detail.projekt || "–"} · Version {detail.structure_version}
                    </p>
                  )}
                </div>
                {detail && (
                  <ExportButtons
                    compact
                    busy={rowExportId === detail.id}
                    onPdf={() => handleAssemblyExport(detail.id, "pdf")}
                    onExcel={() => handleAssemblyExport(detail.id, "xlsx")}
                  />
                )}
              </div>
              {detailLoading || !detail ? (
                <p className="text-sm text-gray-500">Detail wird geladen …</p>
              ) : (
                <>
                  <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4 text-sm">
                    <p>Einzelteilkosten: {euro(detail.einzelteilkosten)}</p>
                    <p>Kaufteilkosten: {euro(detail.kaufteilkosten)}</p>
                    <p>Veredelungskosten: {euro(detail.veredelungskosten)}</p>
                    <p>Investitions-/Werkzeugkosten: {euro(detail.investitionskosten)}</p>
                    <p>VVGK: {euro(detail.vvgk)}</p>
                    <p>Gewinn: {euro(detail.gewinn)}</p>
                    <p>Skonto: {euro(detail.skonto)}</p>
                    <p>Nettoverkaufspreis: {euro(detail.nettoverkaufspreis)}</p>
                    <p>Bruttoverkaufspreis: {euro(detail.bruttoverkaufspreis)}</p>
                    <p>Preis pro Stück: {euro(detail.preis_je_stueck)}</p>
                    <p>Jahresumsatz: {euro(detail.jahresumsatz)}</p>
                    <p>Gesamtsumme: {euro(detail.gesamtsumme)}</p>
                  </div>
                  <h4 className="mb-2 text-sm font-semibold text-gray-900">BOM / Komponentenliste</h4>
                  {detail.bom.length === 0 ? (
                    <p className="text-sm text-gray-500">Keine Komponenten gespeichert.</p>
                  ) : (
                    <table className="w-full min-w-[700px] text-sm">
                      <thead>
                        <tr className="border-b text-left text-gray-500">
                          <th className="py-2 pr-3">Typ</th>
                          <th className="py-2 pr-3">Bezeichnung</th>
                          <th className="py-2 pr-3">Teilenummer</th>
                          <th className="py-2 pr-3 text-right">Menge</th>
                          <th className="py-2 pr-3 text-right">Einzelpreis</th>
                          <th className="py-2 text-right">Summe</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.bom.map((row, index) => (
                          <tr key={`${row.position_type}-${index}`} className="border-b border-gray-100">
                            <td className="py-2 pr-3">{row.position_type}</td>
                            <td className="py-2 pr-3">{row.bezeichnung}</td>
                            <td className="py-2 pr-3">{row.teilenummer || "–"}</td>
                            <td className="py-2 pr-3 text-right tabular-nums">{row.menge}</td>
                            <td className="py-2 pr-3 text-right tabular-nums">{euro(row.einzelpreis)}</td>
                            <td className="py-2 text-right tabular-nums">{euro(row.zwischensumme)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </>
              )}
            </section>
          )}

          <section className="overflow-x-auto rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-4 font-semibold text-gray-900">Investitionsübersicht</h3>
            {data.investments.length === 0 ? (
              <p className="text-sm text-gray-500">Keine Investitionen in der aktuellen Auswahl.</p>
            ) : (
              <>
                <table className="mb-4 w-full min-w-[1100px] text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-500">
                      <th className="py-2 pr-3">Bezeichnung</th>
                      <th className="py-2 pr-3">Typ</th>
                      <th className="py-2 pr-3">Projekt</th>
                      <th className="py-2 pr-3 text-right">Betrag</th>
                      <th className="py-2 pr-3">Lieferant</th>
                      <th className="py-2 pr-3">Status</th>
                      <th className="py-2 pr-3">Bestelldatum</th>
                      <th className="py-2 pr-3">Liefertermin</th>
                      <th className="py-2 pr-3 text-right">Amortisationsvolumen</th>
                      <th className="py-2 text-right">Kostenanteil/Teil</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.investments.map((row) => (
                      <tr key={row.id} className="border-b border-gray-100">
                        <td className="py-2 pr-3">{row.bezeichnung}</td>
                        <td className="py-2 pr-3">{row.typ}</td>
                        <td className="py-2 pr-3">{row.projekt || "–"}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{euro(row.betrag)}</td>
                        <td className="py-2 pr-3">{row.lieferant || "–"}</td>
                        <td className="py-2 pr-3">{row.status}</td>
                        <td className="py-2 pr-3 whitespace-nowrap">{formatDay(row.bestelldatum)}</td>
                        <td className="py-2 pr-3 whitespace-nowrap">{formatDay(row.liefertermin)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">
                          {row.amortisationsvolumen == null ? "–" : int(row.amortisationsvolumen)}
                        </td>
                        <td className="py-2 text-right tabular-nums">{euro(row.kostenanteil_pro_teil)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <h4 className="mb-2 text-sm font-semibold text-gray-900">Gesamtinvestitionsvolumen je Projekt</h4>
                <table className="w-full max-w-xl text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-500">
                      <th className="py-2 pr-3">Projekt</th>
                      <th className="py-2 text-right">Betrag</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.investment_by_project.map((row) => (
                      <tr key={row.projekt} className="border-b border-gray-100">
                        <td className="py-2 pr-3">{row.projekt}</td>
                        <td className="py-2 text-right tabular-nums">{euro(row.betrag)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
