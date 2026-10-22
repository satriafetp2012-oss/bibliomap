import { useTranslation } from "react-i18next";

export interface Series {
  label: string;
  bars: number[];
  line?: (number | null)[];
  categories: string[];
}

const W = 720;
const H = 260;
const PAD = { top: 16, right: 48, bottom: 36, left: 48 };

/** Documents per year as bars, with an optional mean-citations line. */
export function BarLineChart({ series }: { series: Series }) {
  const { t } = useTranslation();
  const n = series.bars.length;
  if (n === 0) return <p className="muted">{t("stats.empty")}</p>;

  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const maxBar = Math.max(...series.bars, 1);
  const lineValues = (series.line ?? []).filter((v): v is number => v !== null);
  const maxLine = Math.max(...lineValues, 1);

  const bandWidth = plotW / n;
  const barWidth = Math.max(2, bandWidth * 0.7);
  const x = (i: number) => PAD.left + bandWidth * (i + 0.5);
  const yBar = (v: number) => PAD.top + plotH - (v / maxBar) * plotH;
  const yLine = (v: number) => PAD.top + plotH - (v / maxLine) * plotH;

  // Thin the tick labels so they never overlap.
  const step = Math.max(1, Math.ceil(n / 12));
  const linePath = (series.line ?? [])
    .map((v, i) => (v === null ? null : `${x(i)},${yLine(v)}`))
    .filter((p): p is string => p !== null)
    .join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label={series.label}>
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line
            x1={PAD.left}
            x2={W - PAD.right}
            y1={PAD.top + plotH * f}
            y2={PAD.top + plotH * f}
            className="chart-grid"
          />
          <text x={PAD.left - 8} y={PAD.top + plotH * f + 4} className="chart-tick end">
            {Math.round(maxBar * (1 - f))}
          </text>
          {lineValues.length > 0 && (
            <text x={W - PAD.right + 8} y={PAD.top + plotH * f + 4} className="chart-tick accent">
              {Math.round(maxLine * (1 - f))}
            </text>
          )}
        </g>
      ))}
      {series.bars.map((value, i) => (
        <rect
          key={series.categories[i]}
          x={x(i) - barWidth / 2}
          y={yBar(value)}
          width={barWidth}
          height={Math.max(0, PAD.top + plotH - yBar(value))}
          className="chart-bar"
        >
          <title>{`${series.categories[i]}: ${value}`}</title>
        </rect>
      ))}
      {linePath && <polyline points={linePath} className="chart-line" />}
      {series.categories.map((label, i) =>
        i % step === 0 ? (
          <text key={label} x={x(i)} y={H - 12} className="chart-tick middle">
            {label}
          </text>
        ) : null,
      )}
    </svg>
  );
}
