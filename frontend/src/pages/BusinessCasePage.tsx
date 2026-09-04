import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  businessCasePdfUrl,
  businessCaseXlsxUrl,
  getBusinessCaseOverview,
  upsertManualPrice,
} from "../api/businessCase";
import { downloadReport } from "../api/reports";
import {
  HierarchySelector,
  type HierarchySelection,
} from "../components/hierarchy/HierarchySelector";
import { ProfitabilityGauge } from "../components/businessCase/ProfitabilityGauge";
import { RevenueDevelopmentChart } from "../components/businessCase/RevenueDevelopmentChart";
import { DecimalInputField } from "../components/DecimalInputField";
import { useAuth } from "../context/AuthContext";
import { EINMALZAHLUNG_HINWEIS } from "../types/investition";
import type {
  BusinessCaseAssemblyRow,
  BusinessCaseInvestmentRow,
  BusinessCaseKpiSummary,
  BusinessCasePartRow,
  BusinessCaseResponse,
  PriceEditTarget,
} from "../types/businessCase";
import { coerceFormDecimal, formatDecimalForInputDe } from "../utils/decimalInput";
import {
  formatCost,
  formatEuro,
  formatEbitWithPercent,
  formatInvestmentOptional,
  formatInteger,
  formatManualPrice,
  formatMarginWithPercent,
  formatPercentOrDash,
  formatRevenueEuro,
  marginClass,
  valueColorClass,
} from "./businessCaseFormatting";

const emptyHierarchy = (): HierarchySelection => ({
  customer_id: null,
  program_id: null,
  project_id: null,
});

function KpiCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "positive" | "negative" | "neutral";
}) {
  const toneClass =
    tone === "positive"
      ? "text-emerald-700"
      : tone === "negative"
        ? "text-red-700"
        : "text-gray-900";
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`mt-2 text-xl font-semibold ${toneClass}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-gray-500">{hint}</div>}
    </div>
  );
}

function toneFromValue(value: number | null | undefined): "positive" | "negative" | "neutral" {
  if (value == null || Number.isNaN(value) || value === 0) return "neutral";
  return value > 0 ? "positive" : "negative";
}

function ScenarioComparisonTable({ summary }: { summary: BusinessCaseKpiSummary }) {
  const rows = [
    {
      label: "Umsatz",
      bottom: summary.operating.bottom_price_revenue_total,
      actual: summary.operating.actual_revenue_total,
      isRevenue: true,
    },
    {
      label: "Operative Kosten",
      bottom: summary.operating.cost_total,
      actual: summary.operating.cost_total,
      isCost: true,
    },
    {
      label: "EBIT",
      bottom: summary.operating.ebit_bottom,
      actual: summary.operating.ebit_actual,
      isMoney: true,
    },
    {
      label: "EBIT %",
      bottom: summary.operating.ebit_bottom_pct,
      actual: summary.operating.ebit_actual_pct,
      isPercent: true,
    },
    {
      label: "ROI inkl. CAPEX",
      bottom: summary.capital.roi_incl_capex_bottom_pct,
      actual: summary.capital.roi_incl_capex_actual_pct,
      isPercent: true,
    },
    {
      label: "Operativer ROI ohne CAPEX",
      bottom: summary.operating.roi_operating_bottom_pct,
      actual: summary.operating.roi_operating_actual_pct,
      isPercent: true,
    },
  ];
  const fmt = (
    value: number | null | undefined,
    opts: { isRevenue?: boolean; isCost?: boolean; isMoney?: boolean; isPercent?: boolean },
  ) => {
    if (value == null) return "–";
    if (opts.isPercent) return formatPercentOrDash(value);
    if (opts.isRevenue) return formatRevenueEuro(value);
    if (opts.isCost) return formatCost(value, true);
    if (opts.isMoney) return formatEuro(value);
    return String(value);
  };
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b text-left text-gray-600">
            <th className="py-2 pr-4">KPI</th>
            <th className="py-2 pr-4 text-right">Bottom Price</th>
            <th className="py-2 text-right">Tatsächlicher Preis</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-gray-100">
              <td className="py-2 pr-4 font-medium">{row.label}</td>
              <td
                className={`py-2 pr-4 text-right ${row.isPercent || row.isMoney ? valueColorClass(row.bottom ?? null) : ""}`}
              >
                {fmt(row.bottom, row)}
              </td>
              <td
                className={`py-2 text-right ${row.isPercent || row.isMoney ? valueColorClass(row.actual ?? null) : ""}`}
              >
                {fmt(row.actual, row)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BreakdownList({
  title,
  items,
}: {
  title: string;
  items: Array<{ label: string; value: string }>;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
      <h4 className="mb-3 font-semibold text-gray-800">{title}</h4>
      <dl className="space-y-2 text-sm">
        {items.map((item) => (
          <div key={item.label} className="flex items-start justify-between gap-4">
            <dt className="text-gray-600">{item.label}</dt>
            <dd className="font-medium text-gray-900">{item.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function InvestmentDashboardHead({ summary }: { summary: BusinessCaseKpiSummary }) {
  const inv = summary.investments_operating;
  return (
    <div className="mb-4 grid gap-3 lg:grid-cols-2">
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">
        <h4 className="font-semibold text-amber-900">Operative Investitionen (ohne CAPEX)</h4>
        <div className="mt-2 grid gap-1">
          <div>Kosten: {formatEuro(summary.capital.operative_investment_cost_total)}</div>
          <div>
            Bottom-Price-Erlös:{" "}
            {summary.revenue_breakdown.investments_bottom_price_revenue != null
              ? formatRevenueEuro(summary.revenue_breakdown.investments_bottom_price_revenue)
              : "–"}
          </div>
          <div>
            Tatsächlicher Erlös:{" "}
            {summary.revenue_breakdown.investments_actual_revenue != null
              ? formatRevenueEuro(summary.revenue_breakdown.investments_actual_revenue)
              : "–"}
          </div>
          <div className={valueColorClass(inv.ebit_bottom)}>
            EBIT Bottom: {formatEbitWithPercent(inv.ebit_bottom, inv.ebit_bottom_pct)}
          </div>
          <div className={valueColorClass(inv.ebit_actual)}>
            EBIT tatsächlich: {formatEbitWithPercent(inv.ebit_actual, inv.ebit_actual_pct)}
          </div>
        </div>
      </div>
      <div className="rounded-lg border border-slate-300 bg-slate-50 p-4 text-sm">
        <h4 className="font-semibold text-slate-800">CAPEX / Werksinvestitionen</h4>
        <div className="mt-2 grid gap-1">
          <div>Kosten einmalig: {formatEuro(summary.capex.cost_total)}</div>
          <div className="text-xs text-slate-600">{summary.capex.note}</div>
          <div>
            Anteil gebundenes Kapital:{" "}
            {formatPercentOrDash(summary.capex.bound_capital_share_pct)}
          </div>
          <div>Gebundenes Projektkapital gesamt: {formatEuro(summary.capital.bound_capital_total)}</div>
        </div>
      </div>
    </div>
  );
}

function InvestmentTable({
  rows,
  mode,
}: {
  rows: BusinessCaseInvestmentRow[];
  mode: "capex" | "entwicklung" | "other";
}) {
  if (rows.length === 0) return null;
  const showMargins = mode !== "capex";
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b text-left text-gray-600">
            <th className="py-2 pr-3">Bezeichnung</th>
            <th className="py-2 pr-3">Zuordnung</th>
            {mode === "capex" && <th className="py-2 pr-3">Zahlungsart</th>}
            <th className="py-2 pr-3">Kosten einmalig</th>
            {showMargins && <th className="py-2 pr-3">Bottom Price einmalig</th>}
            {showMargins && <th className="py-2 pr-3">Erlös einmalig</th>}
            {showMargins && <th className="py-2 pr-3">Erlös−Kosten</th>}
            {showMargins && <th className="py-2 pr-3">Erlös−Bottom</th>}
            <th className="py-2">Hinweis</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((inv) => (
            <tr key={inv.id} className="border-b border-gray-100">
              <td className="py-2 pr-3">{inv.bezeichnung}</td>
              <td className="py-2 pr-3">{inv.zuordnung}</td>
              {mode === "capex" && <td className="py-2 pr-3">{inv.payment_type}</td>}
              <td className="py-2 pr-3">{formatEuro(inv.cost_amount)}</td>
              {showMargins && (
                <td className="py-2 pr-3">{formatInvestmentOptional(inv.bottom_price)}</td>
              )}
              {showMargins && (
                <td className="py-2 pr-3">{formatInvestmentOptional(inv.revenue_amount)}</td>
              )}
              {showMargins && (
                <td className={`py-2 pr-3 ${marginClass(inv.margin_revenue_minus_cost)}`}>
                  {inv.revenue_amount != null
                    ? formatMarginWithPercent(
                        inv.margin_revenue_minus_cost,
                        inv.margin_revenue_minus_cost_pct,
                      )
                    : "–"}
                </td>
              )}
              {showMargins && (
                <td className={`py-2 pr-3 ${marginClass(inv.margin_revenue_minus_bottom_price)}`}>
                  {inv.revenue_amount != null && inv.bottom_price != null
                    ? formatMarginWithPercent(
                        inv.margin_revenue_minus_bottom_price,
                        inv.margin_revenue_minus_bottom_price_pct,
                      )
                    : "–"}
                </td>
              )}
              <td className="py-2 text-xs text-amber-800">
                {[
                  mode === "capex" ? "nicht EBIT-wirksam, kapitalbindend" : "",
                  inv.hinweis,
                  ...(inv.amount_warnings ?? []),
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CategorySummary({
  title,
  block,
  showMargins = true,
  note,
}: {
  title: string;
  block: {
    count: number;
    cost_amount_total: number;
    bottom_price_total?: number;
    revenue_amount_total?: number;
    margin_revenue_minus_cost_total?: number | null;
    margin_revenue_minus_bottom_price_total?: number | null;
    margin_revenue_minus_cost_pct?: number | null;
    margin_revenue_minus_bottom_price_pct?: number | null;
  };
  showMargins?: boolean;
  note?: string;
}) {
  return (
    <div className="rounded border border-gray-200 p-3 text-sm">
      <h4 className="mb-2 font-semibold">{title}</h4>
      {note && <p className="mb-2 text-xs text-slate-600">{note}</p>}
      <div className="grid gap-1 sm:grid-cols-2">
        <div>Anzahl: {block.count}</div>
        <div>Kosten: {formatEuro(block.cost_amount_total)}</div>
        {showMargins && (
          <>
            <div>Bottom Price: {formatEuro(block.bottom_price_total ?? 0)}</div>
            <div>Erlös: {formatEuro(block.revenue_amount_total ?? 0)}</div>
            <div className={marginClass(block.margin_revenue_minus_cost_total ?? null)}>
              Erlös − Kosten:{" "}
              {formatMarginWithPercent(
                block.margin_revenue_minus_cost_total ?? null,
                block.margin_revenue_minus_cost_pct ?? null,
              )}
            </div>
            <div className={marginClass(block.margin_revenue_minus_bottom_price_total ?? null)}>
              Erlös − Bottom:{" "}
              {formatMarginWithPercent(
                block.margin_revenue_minus_bottom_price_total ?? null,
                block.margin_revenue_minus_bottom_price_pct ?? null,
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function PriceEditDialog({
  target,
  filter,
  canWrite,
  onClose,
  onSaved,
}: {
  target: PriceEditTarget;
  filter: BusinessCaseResponse["filter"];
  canWrite: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [bottomRaw, setBottomRaw] = useState(
    target.row.bottom_price_per_piece != null
      ? formatDecimalForInputDe(target.row.bottom_price_per_piece)
      : "",
  );
  const [actualRaw, setActualRaw] = useState(
    target.row.actual_price_per_piece != null
      ? formatDecimalForInputDe(target.row.actual_price_per_piece)
      : "",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    dialogRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const bottom = bottomRaw.trim() ? coerceFormDecimal(bottomRaw, "Bottom Price") : null;
      const actual = actualRaw.trim() ? coerceFormDecimal(actualRaw, "Tatsächlicher Preis") : null;
      await upsertManualPrice({
        customer_id: filter.customer_id,
        program_id: filter.program_id,
        linked_project_id: filter.linked_project_id,
        assignment_type: target.assignmentType,
        object_id: target.row.id,
        bottom_price_per_piece: bottom,
        actual_price_per_piece: actual,
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-2 sm:items-center sm:p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="bc-price-dialog-title"
        className="flex max-h-[min(92dvh,640px)] w-full max-w-lg flex-col overflow-hidden rounded-xl bg-white shadow-xl"
      >
        <header className="flex shrink-0 items-center justify-between border-b px-4 py-3 sm:px-6">
          <h3 id="bc-price-dialog-title" className="text-lg font-semibold">
            Preise bearbeiten
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100"
            aria-label="Schließen"
          >
            ✕
          </button>
        </header>
        <div className="space-y-3 overflow-y-auto px-4 py-4 sm:px-6">
          <p className="text-sm text-gray-600">
            {target.label} · {target.materialNumber}
          </p>
          <p className="text-sm">
            Kosten/Stück:{" "}
            {formatCost(target.row.cost_per_piece, target.row.has_cost_per_piece)}
          </p>
          <p className="text-xs text-gray-500">
            Richtpreis (15 %): {formatEuro(target.row.guide_price_per_piece)} – nur Anzeige, wird nicht
            übernommen
          </p>
          {error && (
            <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {error}
            </div>
          )}
          {canWrite ? (
            <>
              <DecimalInputField
                label="Bottom Price (€ / Stück)"
                rawValue={bottomRaw}
                onRawChange={setBottomRaw}
                className="w-full rounded border px-2 py-1.5 text-sm"
              />
              <DecimalInputField
                label="Tatsächlicher Preis (€ / Stück)"
                rawValue={actualRaw}
                onRawChange={setActualRaw}
                className="w-full rounded border px-2 py-1.5 text-sm"
              />
            </>
          ) : (
            <p className="text-sm text-gray-600">Keine Schreibberechtigung.</p>
          )}
          {target.row.price_warnings.length > 0 && (
            <ul className="list-disc pl-5 text-xs text-amber-800">
              {target.row.price_warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
        </div>
        <footer className="flex shrink-0 justify-end gap-2 border-t px-4 py-3 sm:px-6">
          <button
            type="button"
            onClick={onClose}
            className="rounded border px-3 py-1.5 text-sm hover:bg-gray-50"
          >
            Abbrechen
          </button>
          {canWrite && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void save()}
              className="rounded bg-slate-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              Speichern
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}

export function BusinessCasePage() {
  const { canWrite } = useAuth();
  const [filterHierarchy, setFilterHierarchy] = useState<HierarchySelection>(emptyHierarchy());
  const [data, setData] = useState<BusinessCaseResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [priceEditTarget, setPriceEditTarget] = useState<PriceEditTarget | null>(null);

  const filterReady =
    filterHierarchy.customer_id != null &&
    filterHierarchy.program_id != null &&
    filterHierarchy.project_id != null;

  const loadBusinessCase = useCallback(async () => {
    if (!filterReady) {
      setError("Bitte Kunde, Programm und Projekt auswählen.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await getBusinessCaseOverview({
        customer_id: filterHierarchy.customer_id!,
        program_id: filterHierarchy.program_id!,
        linked_project_id: filterHierarchy.project_id!,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Business Case konnte nicht geladen werden.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [filterHierarchy, filterReady]);

  const reload = () => void loadBusinessCase();

  const resetFilters = () => {
    setFilterHierarchy(emptyHierarchy());
    setData(null);
    setError(null);
  };

  const exportExcel = async () => {
    if (!data) return;
    setExportBusy(true);
    try {
      await downloadReport(
        businessCaseXlsxUrl({
          customer_id: data.customer_id,
          program_id: data.program_id,
          linked_project_id: data.linked_project_id,
        }),
        `business_case_${data.project.replace(/\W+/g, "_")}.xlsx`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export fehlgeschlagen");
    } finally {
      setExportBusy(false);
    }
  };

  const exportPdf = async () => {
    if (!data) return;
    setExportBusy(true);
    try {
      await downloadReport(
        businessCasePdfUrl({
          customer_id: data.customer_id,
          program_id: data.program_id,
          linked_project_id: data.linked_project_id,
        }),
        `business_case_${data.project.replace(/\W+/g, "_")}.pdf`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export fehlgeschlagen");
    } finally {
      setExportBusy(false);
    }
  };

  const priceColumns = (
    <>
      <th className="py-2 pr-3">Kosten/Stück</th>
      <th className="py-2 pr-3">Bottom Price/Stück</th>
      <th className="py-2 pr-3">Tatsächlicher Preis/Stück</th>
      <th className="py-2 pr-3">Richtpreis (15 %)</th>
      <th className="py-2 pr-3">Projektstückzahl</th>
      <th className="py-2 pr-3">Bottom-Umsatz</th>
      <th className="py-2 pr-3">Tatsächlicher Umsatz</th>
      <th className="py-2 pr-3">Kosten gesamt</th>
      <th className="py-2 pr-3">Bottom-Marge</th>
      <th className="py-2 pr-3">Tatsächliche Marge</th>
    </>
  );

  const priceCells = (row: BusinessCasePartRow | BusinessCaseAssemblyRow) => (
    <>
      <td className="py-2 pr-3">{formatCost(row.cost_per_piece, row.has_cost_per_piece)}</td>
      <td className="py-2 pr-3">
        {formatManualPrice(row.bottom_price_per_piece, row.has_manual_bottom_price)}
      </td>
      <td className="py-2 pr-3">
        {formatManualPrice(row.actual_price_per_piece, row.has_manual_actual_price)}
      </td>
      <td
        className="py-2 pr-3 text-gray-600"
        title="Kalkulatorischer Richtwert, nicht der tatsächliche Kundenpreis"
      >
        {formatEuro(row.guide_price_per_piece)}
      </td>
      <td className="py-2 pr-3">{formatInteger(row.project_volume)}</td>
      <td className="py-2 pr-3">
        {row.bottom_price_revenue != null ? formatRevenueEuro(row.bottom_price_revenue) : "–"}
      </td>
      <td className="py-2 pr-3">
        {row.actual_revenue != null ? formatRevenueEuro(row.actual_revenue) : "–"}
      </td>
      <td className="py-2 pr-3">{formatCost(row.cost_total, row.has_cost_per_piece)}</td>
      <td className={`py-2 pr-3 ${marginClass(row.margin_bottom_price_total)}`}>
        {formatMarginWithPercent(row.margin_bottom_price_total, row.margin_bottom_price_total_pct)}
      </td>
      <td className={`py-2 pr-3 ${marginClass(row.margin_actual_total)}`}>
        {formatMarginWithPercent(row.margin_actual_total, row.margin_actual_total_pct)}
      </td>
    </>
  );

  const actionCells = (
    row: BusinessCasePartRow | BusinessCaseAssemblyRow,
    assignmentType: "einzelteil" | "baugruppe",
    label: string,
    linkTo: string,
  ) => (
    <td className="py-2">
      <div className="flex flex-col gap-1">
        {canWrite && (
          <button
            type="button"
            className="text-left text-sm text-blue-700 underline"
            onClick={() =>
              setPriceEditTarget({
                assignmentType,
                row,
                label,
                materialNumber: row.material_number,
              })
            }
          >
            Preise bearbeiten
          </button>
        )}
        <Link to={linkTo} className="text-sm text-blue-700 underline">
          Öffnen
        </Link>
      </div>
    </td>
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Business Case</h2>
        <p className="mt-1 text-sm text-gray-600">
          Projektbezogene Gesamtübersicht mit Verkaufspreis-Szenarien. Einzelteile in Baugruppen werden
          nicht doppelt gezählt. Investitionen separat.
        </p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold">Projektfilter</h3>
        <HierarchySelector
          value={filterHierarchy}
          onChange={(next) => {
            if (next.customer_id !== filterHierarchy.customer_id) {
              setFilterHierarchy({ customer_id: next.customer_id, program_id: null, project_id: null });
            } else if (next.program_id !== filterHierarchy.program_id) {
              setFilterHierarchy({
                customer_id: next.customer_id,
                program_id: next.program_id,
                project_id: null,
              });
            } else {
              setFilterHierarchy(next);
            }
          }}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={loading || !filterReady}
            onClick={() => void loadBusinessCase()}
            className="rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600 disabled:opacity-50"
          >
            Business Case anzeigen
          </button>
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
          >
            Filter zurücksetzen
          </button>
        </div>
      </section>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {data && (
        <>
          <section className="space-y-4">
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold">Business-Case-Dashboard</h3>
                  <p className="mt-1 text-sm text-gray-600">
                    {data.customer} / {data.program} / {data.project}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={exportBusy}
                    onClick={() => void exportExcel()}
                    className="rounded border px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
                  >
                    Excel
                  </button>
                  <button
                    type="button"
                    disabled={exportBusy}
                    onClick={() => void exportPdf()}
                    className="rounded border px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
                  >
                    PDF
                  </button>
                </div>
              </div>

              <div className="mt-6 space-y-4">
                <RevenueDevelopmentChart rows={data.revenue_by_year ?? []} />
                <div className="grid gap-4 lg:grid-cols-2">
                  <ProfitabilityGauge
                    label="EBIT"
                    valuePercent={data.kpis.ebit_actual_total_pct}
                    description="EBIT % zum tatsächlichen Umsatz (bestehende Business-Case-Berechnung, CAPEX nicht enthalten)."
                    data-testid="gauge-ebit"
                  />
                  <ProfitabilityGauge
                    label="ROI"
                    valuePercent={data.kpis.roi_incl_capex_actual_pct}
                    description="ROI % inkl. CAPEX zum tatsächlichen Preis (bestehende Business-Case-Berechnung)."
                    data-testid="gauge-roi"
                  />
                </div>
              </div>

              {data.kpi_summary && (
                <>
                  <div className="mt-6">
                    <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
                      Operative Wirtschaftlichkeit
                    </h4>
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      <KpiCard
                        label="Bottom-Price-Umsatz"
                        value={
                          data.kpis.bottom_price_revenue_total != null
                            ? formatRevenueEuro(data.kpis.bottom_price_revenue_total)
                            : "–"
                        }
                        hint="Teile + Nicht-CAPEX-Investitionen"
                      />
                      <KpiCard
                        label="Tatsächlicher Umsatz"
                        value={
                          data.kpis.actual_revenue_total != null
                            ? formatRevenueEuro(data.kpis.actual_revenue_total)
                            : "–"
                        }
                        hint="Teile + Nicht-CAPEX-Investitionen"
                      />
                      <KpiCard
                        label="Operative Kosten"
                        value={formatCost(
                          data.kpis.operative_cost_total,
                          data.kpis.operative_cost_total != null,
                        )}
                        hint="Teile + Entwicklung + Amortisation/Einmalzahlung"
                      />
                      <KpiCard
                        label="EBIT Bottom Price"
                        value={formatEbitWithPercent(
                          data.kpis.ebit_bottom_total,
                          data.kpis.ebit_bottom_total_pct,
                        )}
                        tone={toneFromValue(data.kpis.ebit_bottom_total)}
                        hint="CAPEX nicht enthalten"
                      />
                      <KpiCard
                        label="EBIT tatsächlicher Preis"
                        value={formatEbitWithPercent(
                          data.kpis.ebit_actual_total,
                          data.kpis.ebit_actual_total_pct,
                        )}
                        tone={toneFromValue(data.kpis.ebit_actual_total)}
                        hint="CAPEX nicht enthalten"
                      />
                      <KpiCard
                        label="Projektstückzahl"
                        value={formatInteger(data.kpis.project_volume_total)}
                        hint={`${data.kpis.anzahl_einzelteile} Einzelteile · ${data.kpis.anzahl_baugruppen} Baugruppen`}
                      />
                    </div>
                  </div>

                  <div className="mt-6">
                    <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
                      Kapitalbindung und Rendite
                    </h4>
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      <KpiCard
                        label="CAPEX gesamt"
                        value={formatEuro(data.kpis.capex_cost_total)}
                        hint="Nicht EBIT-wirksam, kapitalbindend"
                      />
                      <KpiCard
                        label="Sonstige Investitionskosten"
                        value={formatEuro(data.kpis.non_capex_investment_cost_total)}
                        hint="Entwicklung + Amortisation/Einmalzahlung"
                      />
                      <KpiCard
                        label="Gebundenes Projektkapital"
                        value={formatEuro(data.kpis.bound_capital_total)}
                        hint="Operative Kosten + CAPEX"
                      />
                      <KpiCard
                        label="ROI Bottom Price inkl. CAPEX"
                        value={formatPercentOrDash(data.kpis.roi_incl_capex_bottom_pct)}
                        tone={toneFromValue(data.kpis.roi_incl_capex_bottom_pct)}
                      />
                      <KpiCard
                        label="ROI tatsächlich inkl. CAPEX"
                        value={formatPercentOrDash(data.kpis.roi_incl_capex_actual_pct)}
                        tone={toneFromValue(data.kpis.roi_incl_capex_actual_pct)}
                      />
                      <KpiCard
                        label="Operativer ROI ohne CAPEX"
                        value={formatPercentOrDash(data.kpis.roi_operating_bottom_pct)}
                        tone={toneFromValue(data.kpis.roi_operating_bottom_pct)}
                        hint={`tatsächlich: ${formatPercentOrDash(data.kpis.roi_operating_actual_pct)}`}
                      />
                    </div>
                  </div>

                  <div className="mt-6 grid gap-4 lg:grid-cols-2">
                    <BreakdownList
                      title="Umsatzaufteilung"
                      items={[
                        {
                          label: "Teile Bottom Price",
                          value:
                            data.kpi_summary.revenue_breakdown.parts_bottom_price_revenue != null
                              ? formatRevenueEuro(
                                  data.kpi_summary.revenue_breakdown.parts_bottom_price_revenue,
                                )
                              : "–",
                        },
                        {
                          label: "Teile tatsächlich",
                          value:
                            data.kpi_summary.revenue_breakdown.parts_actual_revenue != null
                              ? formatRevenueEuro(data.kpi_summary.revenue_breakdown.parts_actual_revenue)
                              : "–",
                        },
                        {
                          label: "Investitionen Bottom Price",
                          value:
                            data.kpi_summary.revenue_breakdown.investments_bottom_price_revenue != null
                              ? formatRevenueEuro(
                                  data.kpi_summary.revenue_breakdown.investments_bottom_price_revenue,
                                )
                              : "–",
                        },
                        {
                          label: "Investitionen tatsächlich",
                          value:
                            data.kpi_summary.revenue_breakdown.investments_actual_revenue != null
                              ? formatRevenueEuro(
                                  data.kpi_summary.revenue_breakdown.investments_actual_revenue,
                                )
                              : "–",
                        },
                        {
                          label: "Gesamtumsatz Bottom Price",
                          value:
                            data.kpi_summary.revenue_breakdown.total_bottom_price_revenue != null
                              ? formatRevenueEuro(
                                  data.kpi_summary.revenue_breakdown.total_bottom_price_revenue,
                                )
                              : "–",
                        },
                        {
                          label: "Gesamtumsatz tatsächlich",
                          value:
                            data.kpi_summary.revenue_breakdown.total_actual_revenue != null
                              ? formatRevenueEuro(data.kpi_summary.revenue_breakdown.total_actual_revenue)
                              : "–",
                        },
                      ]}
                    />
                    <BreakdownList
                      title="Kostenaufteilung"
                      items={[
                        {
                          label: "Freistehende Einzelteile",
                          value: formatCost(
                            data.kpi_summary.cost_breakdown.parts_standalone,
                            data.kpi_summary.cost_breakdown.parts_standalone != null,
                          ),
                        },
                        {
                          label: "Baugruppen",
                          value: formatCost(
                            data.kpi_summary.cost_breakdown.assemblies,
                            data.kpi_summary.cost_breakdown.assemblies != null,
                          ),
                        },
                        {
                          label: "CAPEX",
                          value: formatEuro(data.kpi_summary.cost_breakdown.capex),
                        },
                        {
                          label: "Entwicklung",
                          value: formatEuro(data.kpi_summary.cost_breakdown.entwicklung),
                        },
                        {
                          label: "Amortisation / Einmalzahlung",
                          value: formatEuro(data.kpi_summary.cost_breakdown.legacy),
                        },
                        {
                          label: "CAPEX (nicht EBIT-wirksam)",
                          value: formatEuro(data.kpi_summary.cost_breakdown.capex),
                        },
                        {
                          label: "Operative Kosten gesamt",
                          value: formatCost(
                            data.kpi_summary.cost_breakdown.operative_total,
                            data.kpi_summary.cost_breakdown.operative_total != null,
                          ),
                        },
                        {
                          label: "Gebundenes Projektkapital",
                          value: formatEuro(data.kpi_summary.cost_breakdown.bound_capital),
                        },
                      ]}
                    />
                  </div>

                  <div className="mt-6">
                    <h4 className="mb-3 font-semibold text-gray-800">Szenariovergleich</h4>
                    <ScenarioComparisonTable summary={data.kpi_summary} />
                    <p className="mt-2 text-xs text-gray-500">{data.kpi_summary.ebit_note}</p>
                    <p className="mt-1 text-xs text-gray-500">{data.kpi_summary.roi_note}</p>
                  </div>
                </>
              )}
              <p className="mt-4 text-xs text-gray-500">{data.revenue_summary.hinweis}</p>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold">Details – Einzelteile (ohne Baugruppen-Bestandteile)</h3>
            {data.parts.length === 0 ? (
              <p className="text-sm text-gray-600">Keine standalone Einzelteile für dieses Projekt.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="py-2 pr-3">Bezeichnung</th>
                      <th className="py-2 pr-3">Materialnr.</th>
                      {priceColumns}
                      <th className="py-2">Aktionen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.parts.map((p) => (
                      <tr key={p.id} className="border-b border-gray-100 align-top">
                        <td className="py-2 pr-3">{p.bezeichnung}</td>
                        <td className="py-2 pr-3">{p.material_number}</td>
                        {priceCells(p)}
                        {actionCells(p, "einzelteil", p.bezeichnung, "/spritzguss")}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold">Baugruppen</h3>
            {data.assemblies.length === 0 ? (
              <p className="text-sm text-gray-600">Keine Baugruppen für dieses Projekt.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="py-2 pr-3">Name</th>
                      <th className="py-2 pr-3">Materialnr.</th>
                      {priceColumns}
                      <th className="py-2">Aktionen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.assemblies.map((a) => (
                      <tr key={a.id} className="border-b border-gray-100 align-top">
                        <td className="py-2 pr-3">{a.name}</td>
                        <td className="py-2 pr-3">{a.material_number}</td>
                        {priceCells(a)}
                        {actionCells(a, "baugruppe", a.name, "/baugruppen")}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold">Details – Investitionen</h3>
            {data.kpi_summary && <InvestmentDashboardHead summary={data.kpi_summary} />}
            {data.investment_financial_summary && (
              <div className="mb-4 grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
                <CategorySummary
                  title="CAPEX / Werksinvestitionen"
                  block={data.investment_financial_summary.capex}
                  showMargins={false}
                  note="Nicht EBIT-wirksam, kapitalbindend"
                />
                <CategorySummary
                  title="Entwicklungsinvestitionen"
                  block={data.investment_financial_summary.entwicklung}
                />
                <CategorySummary
                  title="Amortisation / Einmalzahlung"
                  block={data.investment_financial_summary.legacy}
                />
                <CategorySummary
                  title="Gesamt Investitionskosten"
                  block={data.investment_financial_summary.totals}
                />
              </div>
            )}
            {data.investments.length === 0 ? (
              <p className="text-sm text-gray-600">Keine Investitionen.</p>
            ) : (
              <div className="space-y-6">
                {(data.investments_capex?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="mb-2 font-semibold text-gray-800">CAPEX / Werksinvestitionen</h4>
                    <InvestmentTable rows={data.investments_capex} mode="capex" />
                  </div>
                )}
                {(data.investments_entwicklung?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="mb-2 font-semibold text-gray-800">Entwicklungsinvestitionen</h4>
                    <InvestmentTable rows={data.investments_entwicklung} mode="entwicklung" />
                  </div>
                )}
                {(data.investments_other?.length ?? 0) > 0 && (
                  <div>
                    <h4 className="mb-2 font-semibold text-gray-800">
                      Amortisation / Einmalzahlung
                    </h4>
                    <InvestmentTable rows={data.investments_other} mode="other" />
                  </div>
                )}
              </div>
            )}
            <p className="mt-3 text-xs text-amber-800">{EINMALZAHLUNG_HINWEIS}</p>
          </section>
        </>
      )}

      {!data && !loading && !error && (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-10 text-center text-sm text-gray-600">
          Bitte Kunde, Programm und Projekt wählen und „Business Case anzeigen“ klicken.
        </div>
      )}

      {priceEditTarget && data && (
        <PriceEditDialog
          target={priceEditTarget}
          filter={data.filter}
          canWrite={canWrite}
          onClose={() => setPriceEditTarget(null)}
          onSaved={reload}
        />
      )}
    </div>
  );
}
