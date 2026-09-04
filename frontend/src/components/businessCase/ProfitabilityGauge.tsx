import { useMemo } from "react";

import { useEcharts, type EChartsCoreOption } from "../../hooks/useEcharts";
import { formatPercentOrDash } from "../../pages/businessCaseFormatting";
import {
  GAUGE_COLOR_CRITICAL,
  GAUGE_COLOR_POSITIVE,
  GAUGE_COLOR_WATCH,
  getGaugeState,
} from "../../utils/businessCaseGauge";
import { buildProfitabilityGaugeOption } from "../../utils/businessCaseEchartsOptions";

/** Halbkreis-Container 2:1 – Radius bezieht sich auf die Höhe. */
function GaugeChartGeometry({ option }: { option: EChartsCoreOption }) {
  const { containerProps } = useEcharts(option, {
    className: "aspect-[2/1] h-auto w-full min-w-0",
    "aria-hidden": true,
  });
  return <div {...containerProps} />;
}

function statusBadgeClass(zoneLabel: string, zone: string): string {
  if (zoneLabel === "über Skala") return "border-slate-300 bg-slate-100 text-slate-800";
  if (zone === "critical" || zoneLabel === "negativ") {
    return "border-red-200 bg-red-50 text-red-800";
  }
  if (zone === "watch") return "border-amber-200 bg-amber-50 text-amber-900";
  if (zone === "positive") return "border-emerald-200 bg-emerald-50 text-emerald-900";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

/**
 * Wiederverwendbare EBIT-/ROI-Karte:
 * ECharts nur Geometrie; Wert, Label und Status als separates HTML.
 * Skalenwerte nur in der unteren Legende (nicht am Bogen).
 */
export function EchartsProfitabilityGauge({
  label,
  valuePercent,
  description,
  subtitle,
  formatValue = formatPercentOrDash,
  "data-testid": dataTestId,
}: {
  label: string;
  valuePercent: number | null | undefined;
  description?: string;
  subtitle?: string;
  formatValue?: (value: number | null | undefined) => string;
  "data-testid"?: string;
}) {
  const state = getGaugeState(valuePercent);
  const option = useMemo(
    () => buildProfitabilityGaugeOption(valuePercent),
    [valuePercent],
  );

  const displayValue = formatValue(state.actualValue);
  const ariaLabel = state.isAvailable
    ? `${label} ${displayValue}, Status ${state.zoneLabel}.`
    : `${label} nicht verfügbar.`;

  return (
    <div
      className="profitability-card flex h-full min-w-0 flex-col rounded-xl border border-slate-200 bg-white p-4 sm:p-5"
      data-testid={dataTestId}
    >
      <header className="gauge-card-header flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="text-base font-semibold leading-tight text-slate-900">{label}</h4>
          {subtitle ? (
            <p className="mt-0.5 text-xs font-medium text-slate-500">{subtitle}</p>
          ) : null}
        </div>
        {state.isAvailable ? (
          <span
            className={`shrink-0 whitespace-nowrap rounded-md border px-2 py-0.5 text-[11px] font-semibold ${statusBadgeClass(state.zoneLabel, state.zone)}`}
            data-testid="gauge-header-status"
          >
            {state.zoneLabel}
          </span>
        ) : null}
      </header>

      {description ? (
        <p className="gauge-card-description mt-2 line-clamp-2 text-xs leading-relaxed text-slate-600">
          {description}
        </p>
      ) : null}

      {!state.isAvailable || option == null ? (
        <div className="mt-4 flex flex-1 items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center">
          <div>
            <p className="text-lg font-semibold text-slate-700">nicht verfügbar</p>
            <p className="mt-1 text-xs text-slate-500">
              Kein berechenbarer Prozentwert im aktuellen Business Case.
            </p>
          </div>
        </div>
      ) : (
        <>
          <div
            className="gauge-chart-area mx-auto mt-3 w-full min-w-0 max-w-[22rem] overflow-visible"
            role="img"
            aria-label={ariaLabel}
          >
            <GaugeChartGeometry option={option} />
          </div>

          <div className="gauge-value-area mt-3 flex min-w-0 flex-col items-center gap-0.5 text-center">
            <strong
              className="gauge-value text-[2rem] font-bold leading-none tabular-nums tracking-tight sm:text-[2.25rem]"
              style={{ color: state.zoneColor }}
              data-testid="gauge-value"
            >
              {displayValue}
            </strong>
            <span
              className="gauge-label text-xs font-semibold uppercase tracking-wide text-slate-500"
              data-testid="gauge-label"
            >
              {label}
            </span>
            <span className="sr-only" data-testid="gauge-status">
              {state.zoneLabel}
            </span>
          </div>

          {state.isAboveScale ? (
            <p
              className="gauge-note mt-2 text-center text-xs leading-snug text-slate-500"
              data-testid="gauge-above-scale-note"
            >
              Der Zeiger ist am oberen Skalenende begrenzt.
            </p>
          ) : null}

          <div
            className="gauge-legend mt-auto grid min-w-0 grid-cols-3 gap-2 border-t border-slate-100 pt-3"
            data-testid="gauge-legend"
          >
            <div className="inline-flex min-w-0 items-center gap-1.5 text-xs text-slate-600">
              <span
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                style={{ background: GAUGE_COLOR_CRITICAL }}
                aria-hidden="true"
              />
              <span>0–5&nbsp;%</span>
            </div>
            <div className="inline-flex min-w-0 items-center justify-center gap-1.5 text-xs text-slate-600">
              <span
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                style={{ background: GAUGE_COLOR_WATCH }}
                aria-hidden="true"
              />
              <span>5–9&nbsp;%</span>
            </div>
            <div className="inline-flex min-w-0 items-center justify-end gap-1.5 text-xs text-slate-600">
              <span
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                style={{ background: GAUGE_COLOR_POSITIVE }}
                aria-hidden="true"
              />
              <span>9–25&nbsp;%</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/** Alias – EBIT und ROI nutzen dieselbe Komponente. */
export const ProfitabilityGauge = EchartsProfitabilityGauge;
