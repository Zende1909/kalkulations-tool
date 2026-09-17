import { useT } from "../../i18n";
import { formatPercentOrDash } from "../../pages/businessCaseFormatting";
import type { BusinessCaseRevenueYearRow } from "../../types/businessCase";
import {
  buildRevenueChartPoints,
  chooseRevenueScale,
  formatRevenueOnScale,
  revenuePeriodLabel,
  sumDisplayRevenue,
} from "../../utils/businessCaseRevenueChart";

function KpiTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm ring-1 ring-slate-900/5">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-bold tabular-nums tracking-tight text-slate-900 sm:text-2xl">
        {value}
      </div>
      {hint ? <div className="mt-0.5 text-xs text-slate-500">{hint}</div> : null}
    </div>
  );
}

export function BusinessCaseKpiStrip({
  revenueByYear,
  ebitPct,
  roiPct,
}: {
  revenueByYear: BusinessCaseRevenueYearRow[] | null | undefined;
  ebitPct: number | null | undefined;
  roiPct: number | null | undefined;
}) {
  const t = useT();
  const points = buildRevenueChartPoints(revenueByYear);
  const total = sumDisplayRevenue(points);
  const scale = chooseRevenueScale([total, ...points.map((p) => p.display_revenue)]);
  const period = revenuePeriodLabel(points);

  return (
    <div
      className="grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-4"
      data-testid="business-case-kpi-strip"
    >
      <KpiTile
        label={t("businessCase.totalRevenue")}
        value={formatRevenueOnScale(total, scale)}
        hint={t("businessCase.revenueSumHint")}
      />
      <KpiTile
        label={t("businessCase.ebit")}
        value={formatPercentOrDash(ebitPct)}
        hint={t("businessCase.ebitHint")}
      />
      <KpiTile
        label={t("businessCase.roi")}
        value={formatPercentOrDash(roiPct)}
        hint={t("businessCase.roiHint")}
      />
      <KpiTile
        label={t("businessCase.period")}
        value={period ?? t("common.dash")}
        hint={period ? t("businessCase.periodHint") : t("businessCase.noVolumeProfile")}
      />
    </div>
  );
}
