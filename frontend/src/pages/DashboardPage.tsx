import { useCallback, useEffect, useState } from "react";

import { getDashboardSummary } from "../api/dashboard";
import type { DashboardSummary } from "../types/dashboard";

function euro(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "Keine Daten";
  return `${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function int(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "0";
  return value.toLocaleString("de-DE");
}

function formatDate(value: string): string {
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

const KPI_CARDS: Array<{
  key: keyof DashboardSummary["kpis"];
  label: string;
  format: "int" | "euro" | "avg";
}> = [
  { key: "anzahl_projekte", label: "Anzahl Projekte", format: "int" },
  { key: "anzahl_spritzguss_kalkulationen", label: "Spritzguss-Kalkulationen", format: "int" },
  { key: "anzahl_baugruppen", label: "Anzahl Baugruppen", format: "int" },
  { key: "durchschnitt_endpreis_einzelteil", label: "Ø Endpreis je Einzelteil", format: "avg" },
  { key: "durchschnitt_baugruppenpreis", label: "Ø Baugruppenpreis je Stück", format: "avg" },
  { key: "investitionen_gesamt", label: "Investitionen gesamt", format: "euro" },
  { key: "jahresstueckzahl", label: "Jahresstückzahl", format: "int" },
  { key: "umsatzpotenzial_jahr", label: "Umsatzpotenzial / Jahr", format: "euro" },
];

function HorizontalBarChart({
  items,
  unit = "€",
}: {
  items: Array<{ label: string; value: number }>;
  unit?: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-gray-500">Keine Daten</p>;
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
  if (items.length === 0) {
    return <p className="text-sm text-gray-500">Keine Daten</p>;
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
          <span
            className="max-w-[72px] truncate text-center text-xs text-gray-500"
            title={item.label}
          >
            {item.label}
          </span>
        </div>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [projectFilter, setProjectFilter] = useState("");
  const [customerFilter, setCustomerFilter] = useState("");
  const [appliedProject, setAppliedProject] = useState<string | undefined>();
  const [appliedCustomer, setAppliedCustomer] = useState<string | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (project?: string, customer?: string) => {
    setLoading(true);
    setError(null);
    try {
      const summary = await getDashboardSummary({
        project: project || undefined,
        customer: customer || undefined,
      });
      setData(summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dashboard konnte nicht geladen werden");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(appliedProject, appliedCustomer).catch(() => undefined);
  }, [load, appliedProject, appliedCustomer]);

  const applyFilters = () => {
    setAppliedProject(projectFilter || undefined);
    setAppliedCustomer(customerFilter || undefined);
  };

  const resetFilters = () => {
    setProjectFilter("");
    setCustomerFilter("");
    setAppliedProject(undefined);
    setAppliedCustomer(undefined);
  };

  const formatKpi = (key: keyof DashboardSummary["kpis"], format: "int" | "euro" | "avg") => {
    if (!data) return format === "avg" ? "Keine Daten" : "0";
    const value = data.kpis[key];
    if (format === "avg") return euro(value as number | null);
    if (format === "euro") return euro(value as number);
    return int(value as number);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
          <p className="mt-1 text-sm text-gray-600">
            Management- und Kalkulationsübersicht für Projekte und Kunden
          </p>
        </div>
        <button
          type="button"
          disabled={loading}
          onClick={() => load(appliedProject, appliedCustomer)}
          className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
        >
          Aktualisieren
        </button>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-900">Filter</h3>
        <div className="flex flex-wrap items-end gap-3">
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

      {error && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}

      {loading ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-500">
          Dashboard wird geladen …
        </div>
      ) : data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {KPI_CARDS.map(({ key, label, format }) => (
              <div
                key={key}
                className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
              >
                <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                  {label}
                </p>
                <p className="mt-2 text-2xl font-bold tabular-nums text-gray-900">
                  {formatKpi(key, format)}
                </p>
              </div>
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-4 font-semibold text-gray-900">
                Top 10 – Endpreis je Stück
              </h3>
              <HorizontalBarChart
                items={data.price_comparison.map((i) => ({
                  label: `${i.label} (${i.typ})`,
                  value: i.value,
                }))}
              />
            </section>
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-4 font-semibold text-gray-900">
                Investitionsvolumen je Projekt
              </h3>
              <VerticalBarChart
                items={data.investment_by_project.map((i) => ({
                  label: i.projekt,
                  value: i.betrag,
                }))}
              />
            </section>
          </div>

          {data.revenue_by_project.length > 0 && (
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="mb-4 font-semibold text-gray-900">Umsatzpotenzial je Projekt</h3>
              <VerticalBarChart
                items={data.revenue_by_project.map((i) => ({
                  label: i.projekt,
                  value: i.betrag,
                }))}
              />
            </section>
          )}

          <section className="rounded-lg border border-gray-200 bg-white p-4 overflow-x-auto">
            <h3 className="mb-4 font-semibold text-gray-900">Letzte Kalkulationen</h3>
            {data.recent_calculations.length === 0 ? (
              <p className="text-sm text-gray-500">Keine Daten</p>
            ) : (
              <table className="w-full min-w-[800px] text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="py-2 pr-3">Art</th>
                    <th className="py-2 pr-3">Bezeichnung</th>
                    <th className="py-2 pr-3">Nummer</th>
                    <th className="py-2 pr-3">Kunde</th>
                    <th className="py-2 pr-3">Projekt</th>
                    <th className="py-2 pr-3 text-right">Endpreis/St.</th>
                    <th className="py-2 pr-3">Erstellt</th>
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
                      <td className="py-2 pr-3 whitespace-nowrap">{formatDate(row.created_at)}</td>
                      <td className="py-2 whitespace-nowrap">{formatDate(row.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4 overflow-x-auto">
            <h3 className="mb-4 font-semibold text-gray-900">Baugruppen</h3>
            {data.assemblies.length === 0 ? (
              <p className="text-sm text-gray-500">Keine Daten</p>
            ) : (
              <table className="w-full min-w-[700px] text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="py-2 pr-3">Name</th>
                    <th className="py-2 pr-3">Teilenummer</th>
                    <th className="py-2 pr-3">Kunde</th>
                    <th className="py-2 pr-3">Projekt</th>
                    <th className="py-2 pr-3 text-right">Preis/St.</th>
                    <th className="py-2 pr-3 text-right">Jahresstückzahl</th>
                    <th className="py-2 text-right">Jahresumsatz</th>
                  </tr>
                </thead>
                <tbody>
                  {data.assemblies.map((row) => (
                    <tr key={row.id} className="border-b border-gray-100">
                      <td className="py-2 pr-3">{row.name}</td>
                      <td className="py-2 pr-3">{row.teilenummer}</td>
                      <td className="py-2 pr-3">{row.kunde || "–"}</td>
                      <td className="py-2 pr-3">{row.projekt || "–"}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{euro(row.preis_je_stueck)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{int(row.jahresstueckzahl)}</td>
                      <td className="py-2 text-right tabular-nums">{euro(row.jahresumsatz)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4 overflow-x-auto">
            <h3 className="mb-4 font-semibold text-gray-900">Investitionen</h3>
            {data.investments.length === 0 ? (
              <p className="text-sm text-gray-500">Keine Daten</p>
            ) : (
              <table className="w-full min-w-[700px] text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="py-2 pr-3">Bezeichnung</th>
                    <th className="py-2 pr-3">Typ</th>
                    <th className="py-2 pr-3 text-right">Betrag</th>
                    <th className="py-2 pr-3">Projekt</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2">Hinweis</th>
                  </tr>
                </thead>
                <tbody>
                  {data.investments.map((row) => (
                    <tr key={row.id} className="border-b border-gray-100">
                      <td className="py-2 pr-3">{row.bezeichnung}</td>
                      <td className="py-2 pr-3">{row.typ}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{euro(row.betrag)}</td>
                      <td className="py-2 pr-3">{row.projekt || "–"}</td>
                      <td className="py-2 pr-3">{row.status}</td>
                      <td className="py-2 text-amber-800">{row.hinweis}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
