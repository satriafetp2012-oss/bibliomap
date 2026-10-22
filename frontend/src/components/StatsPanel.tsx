import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { workspaceApi } from "../api";
import type { RankedEntity, Statistics } from "../types";
import { BarLineChart } from "./BarLineChart";
import { RankTable } from "./RankTable";

const RANKINGS = ["source", "author", "affiliation", "country", "keyword"] as const;
type Ranking = (typeof RANKINGS)[number];

const FIELD: Record<Ranking, keyof Statistics> = {
  source: "top_sources",
  author: "top_authors",
  affiliation: "top_affiliations",
  country: "top_countries",
  keyword: "top_keywords",
};

function Metric({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="metric">
      <dt>{label}</dt>
      <dd>{value ?? "–"}</dd>
    </div>
  );
}

export function StatsPanel({ workspaceId, version }: { workspaceId: string; version: number }) {
  const { t } = useTranslation();
  const [stats, setStats] = useState<Statistics | null>(null);
  const [ranking, setRanking] = useState<Ranking>("source");

  useEffect(() => {
    let cancelled = false;
    setStats(null);
    void workspaceApi.statistics(workspaceId).then((s) => !cancelled && setStats(s));
    return () => {
      cancelled = true;
    };
  }, [workspaceId, version]);

  if (!stats) return <p role="status">{t("import.loading")}</p>;
  const o = stats.overview;
  if (o.documents === 0) return <p className="muted">{t("stats.empty")}</p>;

  const pct = (v: number | null) => (v === null ? null : `${v}%`);

  return (
    <section>
      <h2>{t("stats.heading")}</h2>
      <p className="muted">{t("stats.help")}</p>

      <h3>{t("stats.overview")}</h3>
      <dl className="metrics">
        <Metric label={t("stats.documents")} value={o.documents} />
        <Metric label={t("stats.sources")} value={o.sources} />
        <Metric label={t("stats.authors")} value={o.authors} />
        <Metric label={t("stats.singleAuthored")} value={o.single_authored} />
        <Metric
          label={t("stats.period")}
          value={o.year_min !== null ? `${o.year_min}–${o.year_max}` : null}
        />
        <Metric label={t("stats.growth")} value={pct(o.annual_growth_rate_pct)} />
        <Metric label={t("stats.totalCitations")} value={o.total_citations} />
        <Metric label={t("stats.meanCitations")} value={o.mean_citations} />
        <Metric label={t("stats.authorsPerDoc")} value={o.mean_authors_per_document} />
        <Metric label={t("stats.collabIndex")} value={o.collaboration_index} />
        <Metric label={t("stats.intlCollab")} value={pct(o.international_coauthorship_pct)} />
        <Metric label={t("stats.keywordsAuthor")} value={o.keywords_author} />
        <Metric label={t("stats.keywordsIndex")} value={o.keywords_index} />
        <Metric label={t("stats.references")} value={o.references} />
      </dl>

      <h3>{t("stats.perYear")}</h3>
      <p className="muted">{t("stats.perYearHelp")}</p>
      <BarLineChart
        series={{
          label: t("stats.perYear"),
          categories: o.documents_per_year.map((y) => String(y.year)),
          bars: o.documents_per_year.map((y) => y.count),
          line: o.documents_per_year.map((y) => y.mean_citations),
        }}
      />

      <h3>{t("stats.topHeading")}</h3>
      <nav className="tabs subtabs">
        {RANKINGS.map((name) => (
          <button
            key={name}
            type="button"
            className={ranking === name ? "tab active" : "tab"}
            aria-pressed={ranking === name}
            onClick={() => setRanking(name)}
          >
            {t(`stats.by.${name}`)}
          </button>
        ))}
      </nav>
      <RankTable rows={stats[FIELD[ranking]] as RankedEntity[]} />

      <h3>{t("stats.lotka")}</h3>
      <p className="muted">{t("stats.lotkaHelp")}</p>
      <dl className="metrics">
        <Metric label={t("stats.lotkaExponent")} value={stats.lotka.exponent} />
        <Metric label={t("stats.lotkaR2")} value={stats.lotka.r_squared} />
        <Metric label={t("stats.lotkaKs")} value={stats.lotka.ks_statistic} />
      </dl>
      <table>
        <thead>
          <tr>
            <th className="num">{t("stats.lotkaCol.n")}</th>
            <th className="num">{t("stats.lotkaCol.authors")}</th>
            <th className="num">{t("stats.lotkaCol.observed")}</th>
            <th className="num">{t("stats.lotkaCol.fitted")}</th>
          </tr>
        </thead>
        <tbody>
          {stats.lotka.rows.slice(0, 12).map((row) => (
            <tr key={row.documents_written}>
              <td className="num">{row.documents_written}</td>
              <td className="num">{row.authors}</td>
              <td className="num">{(row.proportion * 100).toFixed(1)}%</td>
              <td className="num">{(row.fitted_proportion * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>{t("stats.bradford")}</h3>
      <p className="muted">{t("stats.bradfordHelp")}</p>
      <dl className="metrics">
        {stats.bradford.zone_sources.map((sources, i) => (
          <Metric
            key={i}
            label={t("stats.zone", { n: i + 1 })}
            value={t("stats.zoneSummary", {
              sources,
              documents: stats.bradford.zone_documents[i],
            })}
          />
        ))}
        <Metric label={t("stats.multiplier")} value={stats.bradford.multiplier} />
      </dl>
      <table>
        <thead>
          <tr>
            <th className="num">{t("stats.col.rank")}</th>
            <th>{t("stats.by.source")}</th>
            <th className="num">{t("stats.col.documents")}</th>
            <th className="num">{t("stats.zone", { n: "" }).trim()}</th>
          </tr>
        </thead>
        <tbody>
          {stats.bradford.rows.slice(0, 20).map((row) => (
            <tr key={row.key}>
              <td className="num">{row.rank}</td>
              <td>{row.label}</td>
              <td className="num">{row.documents}</td>
              <td className="num">{row.zone}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
