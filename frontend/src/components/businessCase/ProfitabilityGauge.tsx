import { useMemo } from "react";

import { useEcharts } from "../../hooks/useEcharts";
import { formatPercentOrDash } from "../../pages/businessCaseFormatting";
import {
  GAUGE_COLOR_CRITICAL,
  GAUGE_COLOR_POSITIVE,
  GAUGE_COLOR_WATCH,
  getGaugeState,
} from "../../utils/businessCaseGauge";
import { buildProfitabilityGaugeOption } from "../../utils/businessCaseEchartsOptions";
import type { EChartsCoreOption } from "../../hooks/useEcharts";

function GaugeChartHost({ option }: { option: EChartsCoreOption }) {
  const { containerProps } = useEcharts(option, {
    className: "h-44 w-full",
    "aria-hidden": true,
  });
  return <div {...containerProps} />;
}

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
    ? `${label} ${displayValue}, Bereich ${state.zoneLabel}.`
    : `${label} nicht verfügbar.`;

  const badgeClass =
    state.zoneLabel === "über Skala"
      ? "border-slate-300 bg-slate-100 text-slate-800"
      : state.zone === "critical"
        ? "border-red-200 bg-red-50 text-red-800"
        : state.zone === "watch"
          ? "border-amber-200 bg-amber-50 text-amber-900"
          : state.zone === "positive"
            ? "border-emerald-200 bg-emerald-50 text-emerald-900"
            : "border-slate-200 bg-slate-50 text-slate-700";

  return (
    <div
      className="flex h-full flex-col rounded-xl border border-slate-200 bg-white p-5"
      data-testid={dataTestId}
    >
      <div className="mb-1 flex items-start justify-between gap-3">
        <div>
          <h4 className="text-base font-semibold text-slate-900">{label}</h4>
          {subtitle ? <p className="text-xs font-medium text-slate-500">{subtitle}</p> : null}
        </div>
        {state.isAvailable ? (
          <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badgeClass}`}>
            {state.zoneLabel}
          </span>
        ) : null}
      </div>
      {description ? <p className="mb-3 text-xs leading-relaxed text-slate-600">{description}</p> : null}

      {!state.isAvailable || option == null ? (
        <div className="mt-4 flex flex-1 items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-12 text-center">
          <div>
            <p className="text-lg font-semibold text-slate-700">nicht verfügbar</p>
            <p className="mt-1 text-xs text-slate-500">
              Kein berechenbarer Prozentwert im aktuellen Business Case.
            </p>
          </div>
        </div>
      ) : (
        <>
          <div role="img" aria-label={ariaLabel} className="mx-auto w-full max-w-[340px]">
            <GaugeChartHost option={option} />
            <div className="mt-1 text-center">
              <div
                className="text-3xl font-bold tabular-nums tracking-tight sm:text-4xl"
                style={{ color: state.zoneColor }}
              >
                {displayValue}
              </div>
              <div className="mt-0.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                {label}
              </div>
            </div>
          </div>

          {(state.isBelowScale || state.isAboveScale) && (
            <p className="mt-2 text-center text-xs text-slate-600">
              {state.isBelowScale
                ? "Der Zeiger ist am linken Skalenanfang begrenzt."
                : "Der Zeiger ist am oberen Skalenende begrenzt."}
            </p>
          )}

          <ul className="mt-4 flex flex-wrap justify-center gap-x-4 gap-y-1 border-t border-slate-100 pt-3 text-xs text-slate-600">
            <li className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: GAUGE_COLOR_CRITICAL }}
              />
              0–5 % kritisch
            </li>
            <li className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: GAUGE_COLOR_WATCH }}
              />
              5–9 % beobachten
            </li>
            <li className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: GAUGE_COLOR_POSITIVE }}
              />
              9–25 % positiv
            </li>
          </ul>
        </>
      )}
    </div>
  );
}

/** Alias für bestehende Imports. */
export const ProfitabilityGauge = EchartsProfitabilityGauge;
