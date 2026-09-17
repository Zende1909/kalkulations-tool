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
import { useT } from "../i18n";

function euro(value: number | null | undefined, noData = "–"): string {
  if (value == null || Number.isNaN(value)) return noData;
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function int(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "0";
  return value.toLocaleString("de-DE");
}

function formatDate(value: string | null | undefined, dash = "–"): string {
  if (!value) return dash;
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

function formatDay(value: string | null | undefined, dash = "–"): string {
  if (!value) return dash;
  try {
    return new Date(value).toLocaleDateString("de-DE");
  } catch {
    return value;
  }
}

function chartHasValues(items: ChartBarItem[] | Array<{ label: string; value: number }>): boolean {
  return items.some((item) => item.value !== 0);
}

function HorizontalBarChart({
  items,
  unit = "€",
  emptyLabel,
}: {
  items: Array<{ label: string; value: number }>;
  unit?: string;
  emptyLabel: string;
}) {
  if (!chartHasValues(items)) {
    return <p className="text-sm text-gray-500">{emptyLabel}</p>;
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
  emptyLabel,
}: {
  items: Array<{ label: string; value: number }>;
  unit?: string;
  emptyLabel: string;
}) {
  if (!chartHasValues(items)) {
    return <p className="text-sm text-gray-500">{emptyLabel}</p>;
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
  const t = useT();
  const noData = t("dashboard.noDataShort");
  const dash = t("common.dash");
  const kpiCards: Array<{
    key: keyof DashboardSummary["kpis"];
    label: string;
    format: "int" | "euro" | "avg";
  }> = [
    { key: "anzahl_projekte", label: t("dashboard.kpiProjects"), format: "int" },
    { key: "anzahl_spritzguss_kalkulationen", label: t("dashboard.kpiMolded"), format: "int" },
    { key: "anzahl_baugruppen", label: t("dashboard.kpiAssemblies"), format: "int" },
    { key: "investitionen_gesamt", label: t("dashboard.kpiInvestments"), format: "euro" },
    { key: "umsatzpotenzial_jahr", label: t("dashboard.kpiRevenue"), format: "euro" },
    { key: "durchschnitt_preis_pro_stueck", label: t("dashboard.kpiAvgPrice"), format: "avg" },
    { key: "durchschnitt_endpreis_einzelteil", label: t("dashboard.kpiAvgMolded"), format: "avg" },
    { key: "durchschnitt_baugruppenpreis", label: t("dashboard.kpiAvgAssembly"), format: "avg" },
  ];
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
      setError(err instanceof Error ? err.message : t("dashboard.loadFailed"));
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
      setError(err instanceof Error ? err.message : t("common.exportFailed"));
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
      setError(err instanceof Error ? err.message : t("common.exportFailed"));
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
      setError(err instanceof Error ? err.message : t("dashboard.assemblyDetailFailed"));
    } finally {
      setDetailLoading(false);
    }
  };

  const formatKpi = (key: keyof DashboardSummary["kpis"], format: "int" | "euro" | "avg") => {
    if (!data) return format === "avg" ? noData : "0";
    const value = data.kpis[key];
    if (format === "avg") return euro(value as number | null, noData);
    if (format === "euro") return euro(value as number, noData);
    return int(value as number);
  };

  const costChart = detail?.cost_structure?.length ? detail.cost_structure : (data?.cost_structure ?? []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{t("nav.dashboard")}</h2>
          <p className="mt-1 text-sm text-gray-600">{t("dashboard.intro")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={loading}
            onClick={() => load(applied)}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            {t("common.reload")}
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
        <h3 className="mb-3 text-sm font-semibold text-gray-900">{t("common.filter")}</h3>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block text-sm">
            <span className="text-gray-600">{t("project.customer")}</span>
            <select
              className="mt-1 block min-w-[180px] rounded border px-2 py-1.5"
              value={customerFilter}
              onChange={(e) => setCustomerFilter(e.target.value)}
            >
              <option value="">{t("dashboard.allCustomers")}</option>
              {(data?.filter_options.kunden ?? []).map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">{t("project.project")}</span>
            <select
              className="mt-1 block min-w-[180px] rounded border px-2 py-1.5"
              value={projectFilter}
              onChange={(e) => setProjectFilter(e.target.value)}
            >
              <option value="">{t("project.allProjects")}</option>
              {(data?.filter_options.projekte ?? []).map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">{t("dashboard.colStatus")}</span>
            <select
              className="mt-1 block min-w-[160px] rounded border px-2 py-1.5"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">{t("dashboard.allStatuses")}</option>
              {(data?.filter_options.statusse ?? []).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">{t("dashboard.calculationType")}</span>
            <select
              className="mt-1 block min-w-[160px] rounded border px-2 py-1.5"
              value={kalkulationsart}
              onChange={(e) => setKalkulationsart(e.target.value)}
            >
              <option value="">{t("dashboard.allTypes")}</option>
              {(data?.filter_options.kalkulationsarten ?? ["Spritzguss", "Baugruppe"]).map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">{t("dashboard.dateFrom")}</span>
            <input
              type="date"
              className="mt-1 block rounded border px-2 py-1.5"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">{t("dashboard.dateTo")}</span>
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
            {t("dashboard.applyFilters")}
          </button>
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50"
          >
            {t("dashboard.resetFilters")}
          </button>
        </div>
      </section>

      {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-500">
          {t("dashboard.loading")}
        </div>
      ) : data && !data.has_data ? (
        <section className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center">
          <h3 className="text-lg font-semibold text-gray-900">{t("dashboard.noDataTitle")}</h3>
          <p className="mx-auto mt-2 max-w-xl text-sm text-gray-600">
            {data.empty_message || t("dashboard.noDataDefault")}
          </p>
          <button
            type="button"
            onClick={resetFilters}
            className="mt-4 rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600"
          >
            {t("dashboard.resetFilters")}
          </button>
        </section>
      ) : data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {kpiCards.map(({ key, label, format }) => (
              <div key={key} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
                <p className="mt-2 text-2xl font-bold tabular-nums text-gray-900">{formatKpi(key, format)}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-4 font-semibold text-gray-900">
                {t("dashboard.costStructure")} {detail ? `– ${detail.name}` : t("dashboard.costStructureOfAssemblies")}
              </h3>
              <HorizontalBarChart items={costChart} emptyLabel={t("dashboard.noChartData")} />
            </section>
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-4 font-semibold text-gray-900">{t("dashboard.priceComparison")}</h3>
              <HorizontalBarChart
                emptyLabel={t("dashboard.noChartData")}
                items={data.price_comparison.map((i) => ({
                  label: `${i.label} (${i.typ})`,
                  value: i.value,
                }))}
              />
            </section>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-4 font-semibold text-gray-900">{t("dashboard.revenueByProject")}</h3>
              <VerticalBarChart
                emptyLabel={t("dashboard.noChartData")}
                items={data.revenue_by_project.map((i) => ({
                  label: i.projekt,
                  value: i.betrag,
                }))}
              />
            </section>
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-4 font-semibold text-gray-900">{t("dashboard.investmentByProject")}</h3>
              <VerticalBarChart
                emptyLabel={t("dashboard.noChartData")}
                items={data.investment_by_project.map((i) => ({
                  label: i.projekt,
                  value: i.betrag,
                }))}
              />
            </section>
          </div>

          <section className="overflow-x-auto rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-4 font-semibold text-gray-900">{t("dashboard.recentCalculations")}</h3>
            {data.recent_calculations.length === 0 ? (
              <p className="text-sm text-gray-500">{t("dashboard.noCalculations")}</p>
            ) : (
              <table className="w-full min-w-[800px] text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="py-2 pr-3">{t("dashboard.colType")}</th>
                    <th className="py-2 pr-3">{t("dashboard.colDesignation")}</th>
                    <th className="py-2 pr-3">{t("dashboard.colNumber")}</th>
                    <th className="py-2 pr-3">{t("dashboard.colCustomer")}</th>
                    <th className="py-2 pr-3">{t("dashboard.colProject")}</th>
                    <th className="py-2 pr-3 text-right">{t("dashboard.colPricePc")}</th>
                    <th className="py-2">{t("dashboard.colChanged")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_calculations.map((row) => (
                    <tr key={`${row.kalkulationsart}-${row.id}`} className="border-b border-gray-100">
                      <td className="py-2 pr-3">{row.kalkulationsart}</td>
                      <td className="py-2 pr-3">{row.bezeichnung}</td>
                      <td className="py-2 pr-3">{row.nummer}</td>
                      <td className="py-2 pr-3">{row.kunde || dash}</td>
                      <td className="py-2 pr-3">{row.projekt || dash}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{euro(row.endpreis_je_stueck, noData)}</td>
                      <td className="py-2 whitespace-nowrap">{formatDate(row.updated_at, dash)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="overflow-x-auto rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-4 font-semibold text-gray-900">{t("dashboard.recentInvestments")}</h3>
            {data.recent_investments.length === 0 ? (
              <p className="text-sm text-gray-500">{t("dashboard.noInvestments")}</p>
            ) : (
              <table className="w-full min-w-[700px] text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="py-2 pr-3">{t("dashboard.colDesignation")}</th>
                    <th className="py-2 pr-3">{t("dashboard.colInvestmentType")}</th>
                    <th className="py-2 pr-3">{t("dashboard.colProject")}</th>
                    <th className="py-2 pr-3 text-right">{t("dashboard.colAmount")}</th>
                    <th className="py-2">{t("dashboard.colCreated")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_investments.map((row) => (
                    <tr key={row.id} className="border-b border-gray-100">
                      <td className="py-2 pr-3">{row.bezeichnung}</td>
                      <td className="py-2 pr-3">{row.typ}</td>
                      <td className="py-2 pr-3">{row.projekt || dash}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{euro(row.betrag, noData)}</td>
                      <td className="py-2 whitespace-nowrap">{formatDate(row.created_at, dash)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="overflow-x-auto rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-4 font-semibold text-gray-900">{t("dashboard.assemblyOverview")}</h3>
            {data.assemblies.length === 0 ? (
              <p className="text-sm text-gray-500">
                {t("dashboard.noAssemblies")}
              </p>
            ) : (
              <table className="w-full min-w-[980px] text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="py-2 pr-3">{t("dashboard.colAssembly")}</th>
                    <th className="py-2 pr-3">{t("dashboard.colProject")}</th>
                    <th className="py-2 pr-3">{t("dashboard.colCustomer")}</th>
                    <th className="py-2 pr-3">{t("dashboard.colStatus")}</th>
                    <th className="py-2 pr-3 text-right">{t("dashboard.colAnnualQty")}</th>
                    <th className="py-2 pr-3 text-right">{t("dashboard.colPricePc")}</th>
                    <th className="py-2 pr-3 text-right">{t("dashboard.colAnnualRevenue")}</th>
                    <th className="py-2 pr-3">{t("dashboard.colLastCalc")}</th>
                    <th className="py-2">{t("dashboard.colExport")}</th>
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
                      <td className="py-2 pr-3">{row.projekt || dash}</td>
                      <td className="py-2 pr-3">{row.kunde || dash}</td>
                      <td className="py-2 pr-3">{row.status || dash}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{int(row.jahresstueckzahl)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{euro(row.preis_je_stueck, noData)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{euro(row.jahresumsatz, noData)}</td>
                      <td className="py-2 pr-3 whitespace-nowrap">{formatDate(row.letzte_kalkulation, dash)}</td>
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
                    {t("dashboard.assemblyDetail")}{detail ? ` – ${detail.name}` : ""}
                  </h3>
                  {detail && (
                    <p className="mt-1 text-sm text-gray-600">
                      {detail.kunde || dash} · {detail.projekt || dash} · {t("dashboard.version", { version: detail.structure_version })}
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
                <p className="text-sm text-gray-500">{t("dashboard.detailLoading")}</p>
              ) : (
                <>
                  <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4 text-sm">
                    <p>{t("dashboard.moldedCosts")}: {euro(detail.einzelteilkosten, noData)}</p>
                    <p>{t("dashboard.purchasedCosts")}: {euro(detail.kaufteilkosten, noData)}</p>
                    <p>{t("dashboard.finishingCosts")}: {euro(detail.veredelungskosten, noData)}</p>
                    <p>{t("dashboard.investmentToolingCosts")}: {euro(detail.investitionskosten, noData)}</p>
                    <p>{t("dashboard.vvgk")}: {euro(detail.vvgk, noData)}</p>
                    <p>{t("dashboard.profit")}: {euro(detail.gewinn, noData)}</p>
                    <p>{t("dashboard.cashDiscount")}: {euro(detail.skonto, noData)}</p>
                    <p>{t("dashboard.netSalesPrice")}: {euro(detail.nettoverkaufspreis, noData)}</p>
                    <p>{t("dashboard.grossSalesPrice")}: {euro(detail.bruttoverkaufspreis, noData)}</p>
                    <p>{t("dashboard.pricePerPiece")}: {euro(detail.preis_je_stueck, noData)}</p>
                    <p>{t("dashboard.annualRevenue")}: {euro(detail.jahresumsatz, noData)}</p>
                    <p>{t("dashboard.grandTotal")}: {euro(detail.gesamtsumme, noData)}</p>
                  </div>
                  <h4 className="mb-2 text-sm font-semibold text-gray-900">{t("dashboard.bom")}</h4>
                  {detail.bom.length === 0 ? (
                    <p className="text-sm text-gray-500">{t("dashboard.noComponents")}</p>
                  ) : (
                    <table className="w-full min-w-[700px] text-sm">
                      <thead>
                        <tr className="border-b text-left text-gray-500">
                          <th className="py-2 pr-3">{t("dashboard.colBomType")}</th>
                          <th className="py-2 pr-3">{t("dashboard.colDesignation")}</th>
                          <th className="py-2 pr-3">{t("dashboard.colPartNumber")}</th>
                          <th className="py-2 pr-3 text-right">{t("dashboard.colQty")}</th>
                          <th className="py-2 pr-3 text-right">{t("dashboard.colUnitPrice")}</th>
                          <th className="py-2 text-right">{t("dashboard.colSum")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.bom.map((row, index) => (
                          <tr key={`${row.position_type}-${index}`} className="border-b border-gray-100">
                            <td className="py-2 pr-3">{row.position_type}</td>
                            <td className="py-2 pr-3">{row.bezeichnung}</td>
                            <td className="py-2 pr-3">{row.teilenummer || dash}</td>
                            <td className="py-2 pr-3 text-right tabular-nums">{row.menge}</td>
                            <td className="py-2 pr-3 text-right tabular-nums">{euro(row.einzelpreis, noData)}</td>
                            <td className="py-2 text-right tabular-nums">{euro(row.zwischensumme, noData)}</td>
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
            <h3 className="mb-4 font-semibold text-gray-900">{t("dashboard.investmentOverview")}</h3>
            {data.investments.length === 0 ? (
              <p className="text-sm text-gray-500">{t("dashboard.noInvestments")}</p>
            ) : (
              <>
                <table className="mb-4 w-full min-w-[1100px] text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-500">
                      <th className="py-2 pr-3">{t("dashboard.colDesignation")}</th>
                      <th className="py-2 pr-3">{t("dashboard.colInvestmentType")}</th>
                      <th className="py-2 pr-3">{t("dashboard.colProject")}</th>
                      <th className="py-2 pr-3 text-right">{t("dashboard.colAmount")}</th>
                      <th className="py-2 pr-3">{t("dashboard.colSupplier")}</th>
                      <th className="py-2 pr-3">{t("dashboard.colStatus")}</th>
                      <th className="py-2 pr-3">{t("dashboard.colOrderDate")}</th>
                      <th className="py-2 pr-3">{t("dashboard.colDeliveryDate")}</th>
                      <th className="py-2 pr-3 text-right">{t("dashboard.colAmortVolume")}</th>
                      <th className="py-2 text-right">{t("dashboard.colCostSharePc")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.investments.map((row) => (
                      <tr key={row.id} className="border-b border-gray-100">
                        <td className="py-2 pr-3">{row.bezeichnung}</td>
                        <td className="py-2 pr-3">{row.typ}</td>
                        <td className="py-2 pr-3">{row.projekt || dash}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{euro(row.betrag, noData)}</td>
                        <td className="py-2 pr-3">{row.lieferant || dash}</td>
                        <td className="py-2 pr-3">{row.status}</td>
                        <td className="py-2 pr-3 whitespace-nowrap">{formatDay(row.bestelldatum, dash)}</td>
                        <td className="py-2 pr-3 whitespace-nowrap">{formatDay(row.liefertermin, dash)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">
                          {row.amortisationsvolumen == null ? dash : int(row.amortisationsvolumen)}
                        </td>
                        <td className="py-2 text-right tabular-nums">{euro(row.kostenanteil_pro_teil, noData)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <h4 className="mb-2 text-sm font-semibold text-gray-900">{t("dashboard.investmentTotalByProject")}</h4>
                <table className="w-full max-w-xl text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-500">
                      <th className="py-2 pr-3">{t("dashboard.colProject")}</th>
                      <th className="py-2 text-right">{t("dashboard.colAmount")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.investment_by_project.map((row) => (
                      <tr key={row.projekt} className="border-b border-gray-100">
                        <td className="py-2 pr-3">{row.projekt}</td>
                        <td className="py-2 text-right tabular-nums">{euro(row.betrag, noData)}</td>
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
