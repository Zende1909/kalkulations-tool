import { useCallback, useState } from "react";
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
} from "../types/businessCase";
import { coerceFormDecimal, formatDecimalForInputDe } from "../utils/decimalInput";

function euro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "–";
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function manualPrice(value: number | null | undefined, hasManual: boolean): string {
  if (!hasManual || value == null) return "nicht hinterlegt";
  return euro(value);
}

function marginClass(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "";
  return value < 0 ? "text-red-700" : "";
}

function int(value: number | null | undefined): string {
  if (value == null) return "–";
  return value.toLocaleString("de-DE");
}

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
    margin_bottom_price_minus_cost_total: number | null;
  };
}) {
  return (
    <div className="rounded border border-gray-200 p-3 text-sm">
      <h4 className="mb-2 font-semibold">{title}</h4>
      <div className="grid gap-1 sm:grid-cols-2">
        <div>Anzahl: {block.count}</div>
        <div>Kosten: {euro(block.cost_amount_total)}</div>
        <div>Bottom Price: {euro(block.bottom_price_total)}</div>
        <div>Erlös: {euro(block.revenue_amount_total)}</div>
        <div className={marginClass(block.margin_revenue_minus_cost_total)}>
          Erlös − Kosten: {euro(block.margin_revenue_minus_cost_total)}
        </div>
      </div>
    </div>
  );
}

function ManualPriceEditor({
  row,
  assignmentType,
  filter,
  canWrite,
  onSaved,
}: {
  row: BusinessCasePartRow | BusinessCaseAssemblyRow;
  assignmentType: "einzelteil" | "baugruppe";
  filter: BusinessCaseResponse["filter"];
  canWrite: boolean;
  onSaved: () => void;
}) {
  const [bottomRaw, setBottomRaw] = useState(
    row.bottom_price_per_piece != null ? formatDecimalForInputDe(row.bottom_price_per_piece) : "",
  );
  const [actualRaw, setActualRaw] = useState(
    row.actual_price_per_piece != null ? formatDecimalForInputDe(row.actual_price_per_piece) : "",
  );
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      const bottom = bottomRaw.trim()
        ? coerceFormDecimal(bottomRaw, "Bottom Price")
        : null;
      const actual = actualRaw.trim()
        ? coerceFormDecimal(actualRaw, "Tatsächlicher Preis")
        : null;
      await upsertManualPrice({
        customer_id: filter.customer_id,
        program_id: filter.program_id,
        linked_project_id: filter.linked_project_id,
        assignment_type: assignmentType,
        object_id: row.id,
        bottom_price_per_piece: bottom,
        actual_price_per_piece: actual,
      });
      onSaved();
    } finally {
      setBusy(false);
    }
  };

  if (!canWrite) {
    return (
      <div className="text-xs text-gray-600">
        {manualPrice(row.bottom_price_per_piece, row.has_manual_bottom_price)} /{" "}
        {manualPrice(row.actual_price_per_piece, row.has_manual_actual_price)}
      </div>
    );
  }

  return (
    <div className="flex min-w-[220px] flex-col gap-1">
      <DecimalInputField
        label="Bottom Price (€/Stk.)"
        rawValue={bottomRaw}
        onRawChange={setBottomRaw}
        className="w-full rounded border px-1 py-0.5 text-xs"
      />
      <DecimalInputField
        label="Tatsächlicher Preis (€/Stk.)"
        rawValue={actualRaw}
        onRawChange={setActualRaw}
        className="w-full rounded border px-1 py-0.5 text-xs"
      />
      <button
        type="button"
        disabled={busy}
        onClick={() => void save()}
        className="rounded bg-slate-700 px-2 py-0.5 text-xs text-white disabled:opacity-50"
      >
        Speichern
      </button>
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
      const filename = `business_case_${data.project.replace(/\W+/g, "_")}.xlsx`;
      await downloadReport(
        businessCaseXlsxUrl({
          customer_id: data.customer_id,
          program_id: data.program_id,
          linked_project_id: data.linked_project_id,
        }),
        filename,
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
      const filename = `business_case_${data.project.replace(/\W+/g, "_")}.pdf`;
      await downloadReport(
        businessCasePdfUrl({
          customer_id: data.customer_id,
          program_id: data.program_id,
          linked_project_id: data.linked_project_id,
        }),
        filename,
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
      <th className="py-2 pr-3">Manuelle Preise</th>
    </>
  );

  const priceCells = (row: BusinessCasePartRow | BusinessCaseAssemblyRow, atype: "einzelteil" | "baugruppe") => (
    <>
      <td className="py-2 pr-3">{euro(row.cost_per_piece)}</td>
      <td className="py-2 pr-3">{manualPrice(row.bottom_price_per_piece, row.has_manual_bottom_price)}</td>
      <td className="py-2 pr-3">{manualPrice(row.actual_price_per_piece, row.has_manual_actual_price)}</td>
      <td className="py-2 pr-3 text-gray-600" title="Kalkulatorischer Richtwert, nicht der tatsächliche Kundenpreis">
        {euro(row.guide_price_per_piece)}
      </td>
      <td className="py-2 pr-3">{int(row.project_volume)}</td>
      <td className="py-2 pr-3">{row.bottom_price_revenue != null ? euro(row.bottom_price_revenue) : "–"}</td>
      <td className="py-2 pr-3">{row.actual_revenue != null ? euro(row.actual_revenue) : "–"}</td>
      <td className="py-2 pr-3">{euro(row.cost_total)}</td>
      <td className="py-2 pr-3">
        {data && (
          <ManualPriceEditor
            row={row}
            assignmentType={atype}
            filter={data.filter}
            canWrite={canWrite}
            onSaved={reload}
          />
        )}
        {row.price_warnings.length > 0 && (
          <ul className="mt-1 list-disc pl-4 text-xs text-amber-800">
            {row.price_warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}
      </td>
    </>
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
              setFilterHierarchy({ customer_id: next.customer_id, program_id: next.program_id, project_id: null });
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
          <button type="button" onClick={resetFilters} className="rounded-md border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50">
            Filter zurücksetzen
          </button>
        </div>
      </section>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
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
                ["Gesamtkosten", euro(data.kpis.cost_total)],
                ["Bottom-Price-Umsatz", data.kpis.bottom_price_revenue_total != null ? euro(data.kpis.bottom_price_revenue_total) : "–"],
                ["Tatsächlicher Umsatz", data.kpis.actual_revenue_total != null ? euro(data.kpis.actual_revenue_total) : "–"],
                ["Bottom-Price-Marge", euro(data.kpis.margin_bottom_price_total)],
                ["Tatsächliche Marge", euro(data.kpis.margin_actual_total)],
                ["Projektstückzahl", int(data.kpis.project_volume_total)],
                ["Einzelteile (ohne BG-Anteil)", String(data.kpis.anzahl_einzelteile)],
                ["Ausgeschlossen (in BG)", String(data.kpis.anzahl_einzelteile_in_baugruppen_ausgeschlossen)],
                ["Baugruppen", String(data.kpis.anzahl_baugruppen)],
                ["Investitionen", String(data.kpis.anzahl_investitionen)],
              ].map(([label, value]) => (
                <div key={label} className="rounded border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">{label}</div>
                  <div className={`mt-1 font-semibold ${label.includes("Marge") ? marginClass(typeof value === "string" ? null : (value as number)) : ""}`}>
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
                        {priceCells(p, "einzelteil")}
                        <td className="py-2">
                          <Link to="/spritzguss" className="text-blue-700 underline">
                            Öffnen
                          </Link>
                        </td>
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
                        {priceCells(a, "baugruppe")}
                        <td className="py-2">
                          <Link to="/baugruppen" className="text-blue-700 underline">
                            Öffnen
                          </Link>
                        </td>
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
                <FinancialSummaryBlock title="Materialnummernbezogen" block={data.investment_financial_summary.material_assignments} />
                <FinancialSummaryBlock title="Gesamtprojekt" block={data.investment_financial_summary.project_assignments} />
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
                        <td className="py-2 pr-3">{inv.material_number || (inv.assignment_type === "gesamtprojekt" ? "Gesamtprojekt" : "–")}</td>
                        <td className="py-2 pr-3 text-xs">
                          {inv.customer_name} / {inv.program_name} / {inv.project_name}
                        </td>
                        <td className="py-2 pr-3">{euro(inv.cost_amount)}</td>
                        <td className="py-2 pr-3">{euro(inv.bottom_price)}</td>
                        <td className="py-2 pr-3">{euro(inv.revenue_amount)}</td>
                        <td className={`py-2 pr-3 ${marginClass(inv.margin_revenue_minus_cost)}`}>
                          {euro(inv.margin_revenue_minus_cost)}
                        </td>
                        <td className={`py-2 pr-3 ${marginClass(inv.margin_revenue_minus_bottom_price)}`}>
                          {euro(inv.margin_revenue_minus_bottom_price)}
                        </td>
                        <td className="py-2 text-amber-800 text-xs">
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
    </div>
  );
}
