import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { workspaceApi } from "../api";
import type { ExclusionReason, PrismaFlow } from "../types";

const W = 760;
const BOX = { w: 300, h: 64, rx: 8 };
const LEFT = 40;
const RIGHT = 420;

interface Props {
  workspaceId: string;
  version: number;
}

export function PrismaDiagram({ workspaceId, version }: Props) {
  const { t } = useTranslation();
  const [flow, setFlow] = useState<PrismaFlow | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    let cancelled = false;
    void workspaceApi.prisma(workspaceId).then((f) => !cancelled && setFlow(f));
    return () => {
      cancelled = true;
    };
  }, [workspaceId, version]);

  if (!flow) return <p role="status">{t("import.loading")}</p>;

  const n = (value: number | null) => (value === null ? t("prisma.unknown") : String(value));
  const reasons = Object.entries(flow.automation_ineligible_by_reason) as [
    ExclusionReason,
    number,
  ][];

  // Rows: identification, removals, screening, retrieval, eligibility, included.
  const rows = [60, 170, 280, 370, 460, 560];

  function download() {
    const svg = svgRef.current;
    if (!svg) return;
    const blob = new Blob([new XMLSerializer().serializeToString(svg)], {
      type: "image/svg+xml",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "prisma.svg";
    link.click();
    URL.revokeObjectURL(url);
  }

  const Box = ({
    x,
    y,
    lines,
    muted,
  }: {
    x: number;
    y: number;
    lines: string[];
    muted?: boolean;
  }) => (
    <g>
      <rect
        x={x}
        y={y}
        width={BOX.w}
        height={BOX.h + (lines.length > 2 ? (lines.length - 2) * 14 : 0)}
        rx={BOX.rx}
        className={muted ? "prisma-box muted-box" : "prisma-box"}
      />
      {lines.map((line, i) => (
        <text key={i} x={x + 12} y={y + 24 + i * 16} className="prisma-text">
          {line}
        </text>
      ))}
    </g>
  );

  const height = rows[5] + 90;
  return (
    <section>
      <h2>{t("prisma.heading")}</h2>
      <p className="muted">{t("prisma.help")}</p>
      {flow.pending_duplicate_reviews > 0 && (
        <p role="status">
          {t("prisma.pending", { count: flow.pending_duplicate_reviews })}
        </p>
      )}
      <button type="button" className="secondary" onClick={download}>
        {t("prisma.download")}
      </button>
      <div className="prisma-wrap">
        <svg
          ref={svgRef}
          xmlns="http://www.w3.org/2000/svg"
          viewBox={`0 0 ${W} ${height}`}
          role="img"
          aria-label={t("prisma.heading")}
          className="prisma"
        >
          <defs>
            <marker
              id="prisma-arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M0 0L10 5L0 10z" className="prisma-arrow" />
            </marker>
          </defs>

          <text x={LEFT} y={32} className="prisma-stage">
            {t("prisma.identification")}
          </text>
          <Box
            x={LEFT}
            y={rows[0]}
            lines={[
              t("prisma.identified", { n: flow.identified }),
              ...flow.identified_by_source.map((s) => `• ${s.label}: ${s.count}`),
            ]}
          />
          <Box
            x={RIGHT}
            y={rows[1]}
            lines={[
              t("prisma.removedBefore"),
              t("prisma.duplicates", { n: flow.duplicates_removed }),
              t("prisma.automation", { n: flow.automation_ineligible }),
              ...reasons.map(([reason, count]) => `• ${t(`filters.reasons.${reason}`)}: ${count}`),
              t("prisma.other", { n: flow.other_removed }),
            ]}
          />

          <text x={LEFT} y={rows[2] - 28} className="prisma-stage">
            {t("prisma.screening")}
          </text>
          <Box x={LEFT} y={rows[2]} lines={[t("prisma.screened", { n: flow.screened })]} />
          <Box
            x={RIGHT}
            y={rows[2]}
            muted
            lines={[t("prisma.excludedScreen", { n: n(flow.screening_excluded) })]}
          />
          <Box
            x={LEFT}
            y={rows[3]}
            muted
            lines={[t("prisma.sought", { n: n(flow.sought_for_retrieval) })]}
          />
          <Box
            x={RIGHT}
            y={rows[3]}
            muted
            lines={[t("prisma.notRetrieved", { n: n(flow.not_retrieved) })]}
          />
          <Box
            x={LEFT}
            y={rows[4]}
            muted
            lines={[t("prisma.assessed", { n: n(flow.assessed_for_eligibility) })]}
          />
          <Box
            x={RIGHT}
            y={rows[4]}
            muted
            lines={[t("prisma.reportsExcluded", { n: n(flow.reports_excluded) })]}
          />

          <text x={LEFT} y={rows[5] - 28} className="prisma-stage">
            {t("prisma.included")}
          </text>
          <Box
            x={LEFT}
            y={rows[5]}
            muted
            lines={[t("prisma.studiesIncluded", { n: n(flow.included) })]}
          />

          <g className="prisma-line" markerEnd="url(#prisma-arrow)">
            {[
              // Down the left column.
              `M${LEFT + BOX.w / 2} ${rows[0] + BOX.h + 40}V${rows[2]}`,
              `M${LEFT + BOX.w / 2} ${rows[2] + BOX.h}V${rows[3]}`,
              `M${LEFT + BOX.w / 2} ${rows[3] + BOX.h}V${rows[4]}`,
              `M${LEFT + BOX.w / 2} ${rows[4] + BOX.h}V${rows[5]}`,
              // Across to the removal boxes.
              `M${LEFT + BOX.w / 2} ${rows[1] + 30}H${RIGHT}`,
              `M${LEFT + BOX.w} ${rows[2] + BOX.h / 2}H${RIGHT}`,
              `M${LEFT + BOX.w} ${rows[3] + BOX.h / 2}H${RIGHT}`,
              `M${LEFT + BOX.w} ${rows[4] + BOX.h / 2}H${RIGHT}`,
            ].map((d) => (
              <path key={d} d={d} />
            ))}
          </g>
        </svg>
      </div>
    </section>
  );
}
