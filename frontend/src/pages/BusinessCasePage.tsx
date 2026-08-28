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
import { DecimalInputField } from "../components/DecimalInputField";
import { useAuth } from "../context/AuthContext";
import { EINMALZAHLUNG_HINWEIS } from "../types/investition";
import type {
  BusinessCaseAssemblyRow,
  BusinessCasePartRow,
  BusinessCaseResponse,
  PriceEditTarget,
} from "../types/businessCase";
import { coerceFormDecimal, formatDecimalForInputDe } from "../utils/decimalInput";
import {
  formatCost,
  formatEuro,
  formatInteger,
  formatManualPrice,
  formatMarginWithPercent,
  marginClass,
} from "./businessCaseFormatting";

const emptyHierarchy = (): HierarchySelection => ({
  customer_id: null,
  program_id: null,
  project_id: null,
});

function FinancialSummaryBlock({
  title,
  block,
}: {
  title: string;
  block: {
    count: number;
    cost_amount_total: number;
    bottom_price_total: number;
    revenue_amount_total: number;
    margin_revenue_minus_cost_total: number | null;
    margin_revenue_minus_bottom_price_total: number | null;
    margin_revenue_minus_cost_pct?: number | null;
    margin_revenue_minus_bottom_price_pct?: number | null;
  };
}) {
  return (
    <div className="rounded border border-gray-200 p-3 text-sm">
      <h4 className="mb-2 font-semibold">{title}</h4>
      <div className="grid gap-1 sm:grid-cols-2">
        <div>Anzahl: {block.count}</div>
        <div>Kosten: {formatEuro(block.cost_amount_total)}</div>
        <div>Bottom Price: {formatEuro(block.bottom_price_total)}</div>
        <div>Erlös: {formatEuro(block.revenue_amount_total)}</div>
        <div className={marginClass(block.margin_revenue_minus_cost_total)}>
          Erlös − Kosten:{" "}
          {formatMarginWithPercent(
            block.margin_revenue_minus_cost_total,
            block.margin_revenue_minus_cost_pct,
          )}
        </div>
        <div className={marginClass(block.margin_revenue_minus_bottom_price_total)}>
          Erlös − Bottom:{" "}
          {formatMarginWithPercent(
            block.margin_revenue_minus_bottom_price_total,
            block.margin_revenue_minus_bottom_price_pct,
          )}
        </div>
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
        {row.bottom_price_revenue != null ? formatEuro(row.bottom_price_revenue) : "–"}
      </td>
      <td className="py-2 pr-3">
        {row.actual_revenue != null ? formatEuro(row.actual_revenue) : "–"}
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
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="text-lg font-semibold">Business-Case-Kopf</h3>
            <p className="mt-1 text-sm text-gray-600">
              {data.customer} / {data.program} / {data.project}
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Gesamtkosten", formatCost(data.kpis.cost_total, data.kpis.cost_total != null)],
                [
                  "Bottom-Price-Umsatz",
                  data.kpis.bottom_price_revenue_total != null
                    ? formatEuro(data.kpis.bottom_price_revenue_total)
                    : "–",
                ],
                [
                  "Tatsächlicher Umsatz",
                  data.kpis.actual_revenue_total != null
                    ? formatEuro(data.kpis.actual_revenue_total)
                    : "–",
                ],
                [
                  "Bottom-Price-Marge",
                  formatMarginWithPercent(
                    data.kpis.margin_bottom_price_total,
                    data.kpis.margin_bottom_price_total_pct,
                  ),
                ],
                [
                  "Tatsächliche Marge",
                  formatMarginWithPercent(
                    data.kpis.margin_actual_total,
                    data.kpis.margin_actual_total_pct,
                  ),
                ],
                ["Projektstückzahl", formatInteger(data.kpis.project_volume_total)],
                ["Einzelteile (ohne BG-Anteil)", String(data.kpis.anzahl_einzelteile)],
                ["Ausgeschlossen (in BG)", String(data.kpis.anzahl_einzelteile_in_baugruppen_ausgeschlossen)],
                ["Baugruppen", String(data.kpis.anzahl_baugruppen)],
                ["Investitionen", String(data.kpis.anzahl_investitionen)],
              ].map(([label, value]) => (
                <div key={label} className="rounded border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">{label}</div>
                  <div
                    className={`mt-1 font-semibold ${String(label).includes("Marge") ? marginClass(typeof value === "string" ? null : (value as number)) : ""}`}
                  >
                    {value}
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-gray-500">{data.revenue_summary.hinweis}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={exportBusy}
                onClick={() => void exportExcel()}
                className="rounded border px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                Business Case Excel
              </button>
              <button
                type="button"
                disabled={exportBusy}
                onClick={() => void exportPdf()}
                className="rounded border px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                Business Case PDF
              </button>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="mb-3 font-semibold">Einzelteile (ohne Baugruppen-Bestandteile)</h3>
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
            <h3 className="mb-3 font-semibold">Investitionen</h3>
            {data.investment_financial_summary && (
              <div className="mb-4 grid gap-3 lg:grid-cols-2">
                <FinancialSummaryBlock
                  title="Materialnummernbezogen"
                  block={data.investment_financial_summary.material_assignments}
                />
                <FinancialSummaryBlock
                  title="Gesamtprojekt"
                  block={data.investment_financial_summary.project_assignments}
                />
              </div>
            )}
            {data.investments.length === 0 ? (
              <p className="text-sm text-gray-600">Keine Investitionen.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="py-2 pr-3">Bezeichnung</th>
                      <th className="py-2 pr-3">Zuordnungstyp</th>
                      <th className="py-2 pr-3">Materialnr.</th>
                      <th className="py-2 pr-3">Kunde/Programm/Projekt</th>
                      <th className="py-2 pr-3">Kosten</th>
                      <th className="py-2 pr-3">Bottom Price</th>
                      <th className="py-2 pr-3">Erlös</th>
                      <th className="py-2 pr-3">Erlös−Kosten</th>
                      <th className="py-2 pr-3">Erlös−Bottom</th>
                      <th className="py-2">Hinweis</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.investments.map((inv) => (
                      <tr key={inv.id} className="border-b border-gray-100">
                        <td className="py-2 pr-3">{inv.bezeichnung}</td>
                        <td className="py-2 pr-3">{inv.assignment_type_label || inv.assignment_type || "–"}</td>
                        <td className="py-2 pr-3">
                          {inv.material_number ||
                            (inv.assignment_type === "gesamtprojekt" ? "Gesamtprojekt" : "–")}
                        </td>
                        <td className="py-2 pr-3 text-xs">
                          {inv.customer_name} / {inv.program_name} / {inv.project_name}
                        </td>
                        <td className="py-2 pr-3">{formatEuro(inv.cost_amount)}</td>
                        <td className="py-2 pr-3">{formatEuro(inv.bottom_price)}</td>
                        <td className="py-2 pr-3">{formatEuro(inv.revenue_amount)}</td>
                        <td className={`py-2 pr-3 ${marginClass(inv.margin_revenue_minus_cost)}`}>
                          {formatMarginWithPercent(
                            inv.margin_revenue_minus_cost,
                            inv.margin_revenue_minus_cost_pct,
                          )}
                        </td>
                        <td className={`py-2 pr-3 ${marginClass(inv.margin_revenue_minus_bottom_price)}`}>
                          {formatMarginWithPercent(
                            inv.margin_revenue_minus_bottom_price,
                            inv.margin_revenue_minus_bottom_price_pct,
                          )}
                        </td>
                        <td className="py-2 text-xs text-amber-800">
                          {[inv.hinweis, ...(inv.amount_warnings ?? [])].filter(Boolean).join(" · ")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
