import { formatPercentOrDash } from "../../pages/businessCaseFormatting";
import {
  GAUGE_COLOR_CRITICAL,
  GAUGE_COLOR_POSITIVE,
  GAUGE_COLOR_WATCH,
  GAUGE_SCALE_MAX,
  GAUGE_ZONE_CRITICAL_MAX,
  GAUGE_ZONE_WATCH_MAX,
  getGaugeState,
} from "../../utils/businessCaseGauge";

function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const start = polar(cx, cy, r, startDeg);
  const end = polar(cx, cy, r, endDeg);
  const largeArc = Math.abs(startDeg - endDeg) > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;
}

function percentToAngle(percent: number): number {
  const clamped = Math.min(Math.max(percent, 0), GAUGE_SCALE_MAX);
  return 180 - (clamped / GAUGE_SCALE_MAX) * 180;
}

export function ProfitabilityGauge({
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
  const cx = 160;
  const cy = 150;
  const radius = 118;
  const stroke = 22;

  const marks = [0, GAUGE_ZONE_CRITICAL_MAX, GAUGE_ZONE_WATCH_MAX, GAUGE_SCALE_MAX];
  const needleTip = polar(cx, cy, radius - 18, state.needleAngle);
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

      {!state.isAvailable ? (
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
          <div
            className="relative mx-auto w-full max-w-[320px]"
            role="img"
            aria-label={ariaLabel}
          >
            <svg viewBox="0 0 320 200" className="h-auto w-full" aria-hidden="true">
              <path
                d={arcPath(cx, cy, radius, percentToAngle(0), percentToAngle(GAUGE_ZONE_CRITICAL_MAX))}
                fill="none"
                stroke={GAUGE_COLOR_CRITICAL}
                strokeWidth={stroke}
                strokeLinecap="butt"
              />
              <path
                d={arcPath(
                  cx,
                  cy,
                  radius,
                  percentToAngle(GAUGE_ZONE_CRITICAL_MAX),
                  percentToAngle(GAUGE_ZONE_WATCH_MAX),
                )}
                fill="none"
                stroke={GAUGE_COLOR_WATCH}
                strokeWidth={stroke}
                strokeLinecap="butt"
              />
              <path
                d={arcPath(
                  cx,
                  cy,
                  radius,
                  percentToAngle(GAUGE_ZONE_WATCH_MAX),
                  percentToAngle(GAUGE_SCALE_MAX),
                )}
                fill="none"
                stroke={GAUGE_COLOR_POSITIVE}
                strokeWidth={stroke}
                strokeLinecap="butt"
              />
              {marks.map((mark) => {
                const angle = percentToAngle(mark);
                const outer = polar(cx, cy, radius + 8, angle);
                const inner = polar(cx, cy, radius - stroke / 2 - 4, angle);
                const labelPos = polar(cx, cy, radius + 22, angle);
                return (
                  <g key={mark}>
                    <line
                      x1={inner.x}
                      y1={inner.y}
                      x2={outer.x}
                      y2={outer.y}
                      stroke="#1e293b"
                      strokeWidth={2}
                    />
                    <text
                      x={labelPos.x}
                      y={labelPos.y}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      className="fill-slate-500"
                      fontSize="11"
                    >
                      {mark}%
                    </text>
                  </g>
                );
              })}
              <line
                x1={cx}
                y1={cy}
                x2={needleTip.x}
                y2={needleTip.y}
                stroke="#0f172a"
                strokeWidth={4}
                strokeLinecap="round"
                className="motion-reduce:transition-none motion-safe:transition-[x2,y2] motion-safe:duration-300"
              />
              <circle cx={cx} cy={cy} r={8} fill="#0f172a" />
              <circle cx={cx} cy={cy} r={3.5} fill="#f8fafc" />
            </svg>

            <div className="pointer-events-none absolute inset-x-0 bottom-2 text-center">
              <div
                className="text-3xl font-bold tabular-nums tracking-tight text-slate-900 sm:text-4xl"
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
