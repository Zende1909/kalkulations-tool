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
  formatValue = formatPercentOrDash,
  "data-testid": dataTestId,
}: {
  label: string;
  valuePercent: number | null | undefined;
  description?: string;
  formatValue?: (value: number | null | undefined) => string;
  "data-testid"?: string;
}) {
  const state = getGaugeState(valuePercent);
  const cx = 100;
  const cy = 100;
  const radius = 78;
  const stroke = 14;

  const criticalStart = percentToAngle(0);
  const criticalEnd = percentToAngle(GAUGE_ZONE_CRITICAL_MAX);
  const watchEnd = percentToAngle(GAUGE_ZONE_WATCH_MAX);
  const positiveEnd = percentToAngle(GAUGE_SCALE_MAX);

  const needle = polar(cx, cy, radius - 10, state.needleAngle);
  const displayValue = formatValue(state.actualValue);
  const ariaLabel = state.isAvailable
    ? `${label} ${displayValue}, Bereich ${state.zoneLabel}.`
    : `${label} nicht verfügbar.`;

  return (
    <div
      className="rounded-lg border border-gray-200 bg-white p-4"
      data-testid={dataTestId}
      role="img"
      aria-label={ariaLabel}
    >
      <h4 className="text-sm font-semibold text-gray-900">{label}</h4>
      {description ? <p className="mt-1 text-xs text-gray-600">{description}</p> : null}

      {!state.isAvailable ? (
        <div className="mt-6 rounded-md border border-dashed border-gray-300 bg-gray-50 px-4 py-10 text-center">
          <p className="text-lg font-semibold text-gray-700">nicht verfügbar</p>
          <p className="mt-1 text-xs text-gray-500">
            Kein berechenbarer Prozentwert im aktuellen Business Case.
          </p>
        </div>
      ) : (
        <>
          <div className="relative mx-auto mt-2 w-full max-w-[240px]">
            <svg viewBox="0 0 200 130" className="h-auto w-full" aria-hidden="true">
              <path
                d={arcPath(cx, cy, radius, criticalStart, criticalEnd)}
                fill="none"
                stroke={GAUGE_COLOR_CRITICAL}
                strokeWidth={stroke}
                strokeLinecap="butt"
              />
              <path
                d={arcPath(cx, cy, radius, criticalEnd, watchEnd)}
                fill="none"
                stroke={GAUGE_COLOR_WATCH}
                strokeWidth={stroke}
                strokeLinecap="butt"
              />
              <path
                d={arcPath(cx, cy, radius, watchEnd, positiveEnd)}
                fill="none"
                stroke={GAUGE_COLOR_POSITIVE}
                strokeWidth={stroke}
                strokeLinecap="butt"
              />
              {/* Markierungen bei 5 % und 9 % */}
              {[GAUGE_ZONE_CRITICAL_MAX, GAUGE_ZONE_WATCH_MAX].map((mark) => {
                const angle = percentToAngle(mark);
                const outer = polar(cx, cy, radius + 4, angle);
                const inner = polar(cx, cy, radius - stroke / 2 - 2, angle);
                return (
                  <line
                    key={mark}
                    x1={inner.x}
                    y1={inner.y}
                    x2={outer.x}
                    y2={outer.y}
                    stroke="#334155"
                    strokeWidth={2}
                  />
                );
              })}
              <line
                x1={cx}
                y1={cy}
                x2={needle.x}
                y2={needle.y}
                stroke="#0f172a"
                strokeWidth={3}
                strokeLinecap="round"
                className="motion-safe:transition-[x2,y2] motion-safe:duration-300"
              />
              <circle cx={cx} cy={cy} r={5} fill="#0f172a" />
            </svg>
            <div className="pointer-events-none absolute inset-x-0 bottom-1 text-center">
              <div
                className="text-2xl font-bold tabular-nums text-gray-900"
                style={{ color: state.zoneColor }}
              >
                {displayValue}
              </div>
              <div className="text-xs font-medium uppercase tracking-wide text-gray-600">
                {label}
              </div>
              <div className="text-xs font-medium" style={{ color: state.zoneColor }}>
                {state.zoneLabel}
              </div>
            </div>
          </div>

          <ul className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
            <li className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: GAUGE_COLOR_CRITICAL }} />
              0–5 % kritisch
            </li>
            <li className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: GAUGE_COLOR_WATCH }} />
              5–9 % beobachten
            </li>
            <li className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: GAUGE_COLOR_POSITIVE }} />
              9–25 % positiv
            </li>
          </ul>
          {(state.isBelowScale || state.isAboveScale) && (
            <p className="mt-2 text-xs text-gray-500">
              {state.isBelowScale
                ? "Wert unter 0 %: Zeiger am linken Skalenanfang begrenzt."
                : "Wert über 25 %: Zeiger am rechten Skalenende begrenzt."}
            </p>
          )}
        </>
      )}
    </div>
  );
}
