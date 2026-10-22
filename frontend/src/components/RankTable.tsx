import { useTranslation } from "react-i18next";

import type { RankedEntity } from "../types";

export function RankTable({ rows }: { rows: RankedEntity[] }) {
  const { t } = useTranslation();
  if (rows.length === 0) return <p className="muted">{t("stats.empty")}</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>{t("stats.col.rank")}</th>
          <th>{t("stats.col.label")}</th>
          <th className="num">{t("stats.col.documents")}</th>
          <th className="num">{t("stats.col.citations")}</th>
          <th className="num">{t("stats.col.h")}</th>
          <th className="num">{t("stats.col.g")}</th>
          <th className="num">{t("stats.col.m")}</th>
          <th className="num">{t("stats.col.firstYear")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={row.key}>
            <td className="num">{i + 1}</td>
            <td>{row.label}</td>
            <td className="num">{row.documents}</td>
            <td className="num">{row.citations}</td>
            <td className="num">{row.h_index}</td>
            <td className="num">{row.g_index}</td>
            <td className="num">{row.m_index ?? "–"}</td>
            <td className="num">{row.first_year ?? "–"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
