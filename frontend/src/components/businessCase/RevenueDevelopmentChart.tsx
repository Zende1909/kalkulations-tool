import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatRevenueEuro } from "../../pages/businessCaseFormatting";
import type { BusinessCaseRevenueYearRow } from "../../types/businessCase";
import {
  buildRevenueChartPoints,
  formatChartCurrency,
  hasDisplayableRevenue,
} from "../../utils/businessCaseRevenueChart";

export function RevenueDevelopmentChart({
  rows,
}: {
  rows: BusinessCaseRevenueYearRow[] | null | undefined;
}) {
  const points = buildRevenueChartPoints(rows);
  const hasData = hasDisplayableRevenue(points);
  const chartData = points.map((p) => ({
    year: String(p.calendar_year),
    umsatz: p.display_revenue ?? 0,
    series: p.series,
  }));

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <h4 className="text-sm font-semibold text-gray-900">Umsatzentwicklung</h4>
      <p className="mt-1 text-xs text-gray-600">
        Teileumsatz je Kalenderjahr aus Projektstückzahl × Stückpreis (tatsächlicher Preis,
        sonst Bottom Price). Einmalige Investitionserlöse sind nicht enthalten.
      </p>

      {!hasData ? (
        <p className="mt-6 rounded-md border border-dashed border-gray-300 bg-gray-50 px-4 py-10 text-center text-sm text-gray-600">
          Für den ausgewählten Business Case liegen noch keine Umsatzwerte vor.
        </p>
      ) : (
        <>
          <div className="mt-4 h-64 w-full" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 16, right: 8, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="year" tick={{ fill: "#475569", fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis
                  tickFormatter={(v: number) => formatChartCurrency(v)}
                  tick={{ fill: "#475569", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={72}
                  domain={[0, "auto"]}
                />
                <Tooltip
                  formatter={(value) => [
                    formatRevenueEuro(
                      typeof value === "number" ? value : Number(value ?? NaN),
                    ),
                    "Umsatz",
                  ]}
                  labelFormatter={(label) => `Jahr ${label}`}
                  contentStyle={{
                    borderRadius: 8,
                    borderColor: "#e2e8f0",
                    fontSize: 12,
                  }}
                />
                <Bar
                  dataKey="umsatz"
                  fill="#2563eb"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={48}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <table className="mt-4 min-w-full text-sm">
            <caption className="sr-only">
              Umsatz je Kalenderjahr als tabellarische Alternative zum Diagramm
            </caption>
            <thead>
              <tr className="border-b text-left text-gray-600">
                <th className="py-2 pr-4">Jahr</th>
                <th className="py-2 pr-4 text-right">Umsatz</th>
                <th className="py-2 text-right">Serie</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.calendar_year} className="border-b border-gray-100">
                  <td className="py-2 pr-4">{p.calendar_year}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {p.display_revenue != null ? formatRevenueEuro(p.display_revenue) : "–"}
                  </td>
                  <td className="py-2 text-right text-xs text-gray-500">
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
