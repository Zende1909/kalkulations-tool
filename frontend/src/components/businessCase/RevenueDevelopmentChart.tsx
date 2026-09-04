import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatRevenueEuro } from "../../pages/businessCaseFormatting";
import type { BusinessCaseRevenueYearRow } from "../../types/businessCase";
import {
  buildRevenueChartPoints,
  chooseRevenueScale,
  formatRevenueOnScale,
  hasDisplayableRevenue,
  sumDisplayRevenue,
} from "../../utils/businessCaseRevenueChart";

export function RevenueDevelopmentChart({
  rows,
}: {
  rows: BusinessCaseRevenueYearRow[] | null | undefined;
}) {
  const [tableOpen, setTableOpen] = useState(false);
  const points = useMemo(() => buildRevenueChartPoints(rows), [rows]);
  const hasData = hasDisplayableRevenue(points);
  const scale = useMemo(
    () => chooseRevenueScale(points.map((p) => p.display_revenue)),
    [points],
  );
  const total = sumDisplayRevenue(points);
  const lastYear = points.length > 0 ? points[points.length - 1].calendar_year : null;
  const chartData = points.map((p) => ({
    year: String(p.calendar_year),
    umsatz: p.display_revenue ?? 0,
    series: p.series,
    isLatest: p.calendar_year === lastYear,
  }));
  const seriesLabel =
    points.find((p) => p.series !== "none")?.series === "bottom"
      ? "Bottom Price"
      : "tatsächlich";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-base font-semibold text-slate-900">Umsatzentwicklung</h4>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-slate-600">
            Umsatz je Kalenderjahr aus Projektstückzahl × Stückpreis ({seriesLabel}). Einmalige
            Investitionserlöse sind nicht enthalten.
          </p>
        </div>
        {hasData ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-right">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Gesamtumsatz
            </div>
            <div className="text-sm font-bold tabular-nums text-slate-900">
              {formatRevenueOnScale(total, scale)}
            </div>
          </div>
        ) : null}
      </div>

      {!hasData ? (
        <p className="mt-5 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-600">
          Für den ausgewählten Business Case liegen noch keine Umsatzwerte vor.
        </p>
      ) : (
        <>
          <div className="mt-3 grid gap-4 lg:grid-cols-[minmax(0,1fr)_180px]">
            <div className="h-48 w-full min-w-0" aria-hidden="true">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="2 4" vertical={false} stroke="#e2e8f0" />
                  <XAxis
                    dataKey="year"
                    tick={{ fill: "#475569", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={(v: number) => formatRevenueOnScale(v, scale, { compact: true })}
                    tick={{ fill: "#64748b", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={64}
                    domain={[0, "auto"]}
                  />
                  <Tooltip
                    formatter={(value) => [
                      formatRevenueEuro(
                        typeof value === "number" ? value : Number(value ?? NaN),
                      ),
                      `Umsatz (${seriesLabel})`,
                    ]}
                    labelFormatter={(label) => `Jahr ${label}`}
                    contentStyle={{
                      borderRadius: 8,
                      borderColor: "#e2e8f0",
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="umsatz" radius={[6, 6, 0, 0]} maxBarSize={40} isAnimationActive={false}>
                    {chartData.map((entry) => (
                      <Cell
                        key={entry.year}
                        fill={entry.isLatest ? "#1d4ed8" : "#3b82f6"}
                        fillOpacity={entry.isLatest ? 1 : 0.82}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <aside className="hidden rounded-lg border border-slate-100 bg-slate-50/80 p-3 lg:block">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Jahreswerte
              </p>
              <ul className="mt-2 space-y-1.5">
                {points.map((p) => (
                  <li
                    key={p.calendar_year}
                    className="flex items-baseline justify-between gap-2 text-xs"
                  >
                    <span className="text-slate-600">{p.calendar_year}</span>
                    <span className="font-semibold tabular-nums text-slate-900">
                      {formatRevenueOnScale(p.display_revenue, scale, { compact: true })}
                    </span>
                  </li>
                ))}
              </ul>
            </aside>
          </div>

          <div className="mt-3 lg:hidden">
            <button
              type="button"
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              aria-expanded={tableOpen}
              onClick={() => setTableOpen((v) => !v)}
            >
              {tableOpen ? "Jahreswerte ausblenden" : "Jahreswerte anzeigen"}
            </button>
            {tableOpen ? (
              <table className="mt-2 min-w-full text-sm">
                <caption className="sr-only">Umsatz je Kalenderjahr</caption>
                <thead>
                  <tr className="border-b text-left text-slate-600">
                    <th className="py-1.5 pr-3">Jahr</th>
                    <th className="py-1.5 text-right">Umsatz</th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((p) => (
                    <tr key={p.calendar_year} className="border-b border-slate-100">
                      <td className="py-1.5 pr-3">{p.calendar_year}</td>
                      <td className="py-1.5 text-right tabular-nums">
                        {formatRevenueOnScale(p.display_revenue, scale)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
          </div>

          <table className="sr-only">
            <caption>Umsatz je Kalenderjahr als barrierefreie Alternative</caption>
            <thead>
              <tr>
                <th>Jahr</th>
                <th>Umsatz</th>
                <th>Serie</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={`a11y-${p.calendar_year}`}>
                  <td>{p.calendar_year}</td>
                  <td>
                    {p.display_revenue != null ? formatRevenueEuro(p.display_revenue) : "–"}
                  </td>
                  <td>
                    {p.series === "actual"
                      ? "tatsächlich"
                      : p.series === "bottom"
                        ? "Bottom Price"
                        : "–"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
