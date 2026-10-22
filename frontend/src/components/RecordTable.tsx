import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { BibRecord } from "../types";

// Rendering thousands of rows freezes the page; the preview only needs a sample.
const MAX_ROWS = 200;

function formatAuthors(record: BibRecord, more: string): string {
  const names = record.authors.map((a) => a.name);
  return names.length > 3 ? `${names.slice(0, 3).join("; ")} ${more}` : names.join("; ");
}

interface Props {
  records: BibRecord[];
  /** Total rows on the server when only a page was loaded. */
  total?: number;
  /** Optional trailing column, one value per record. */
  extra?: { header: string; values: ReactNode[] };
}

export function RecordTable({ records, total, extra }: Props) {
  const { t } = useTranslation();
  const shown = records.slice(0, MAX_ROWS);

  return (
    <div className="table-wrap">
      <p className="muted">{t("table.showing", { shown: shown.length, total: total ?? records.length })}</p>
      <table>
        <thead>
          <tr>
            <th>{t("table.title")}</th>
            <th>{t("table.authors")}</th>
            <th>{t("table.year")}</th>
            <th>{t("table.source")}</th>
            <th>{t("table.type")}</th>
            <th className="num">{t("table.citedBy")}</th>
            <th>{t("table.doi")}</th>
            {extra && <th>{extra.header}</th>}
          </tr>
        </thead>
        <tbody>
          {shown.map((record, i) => (
            <tr key={record.source_id ?? i}>
              <td>{record.title}</td>
              <td>{formatAuthors(record, t("table.moreAuthors"))}</td>
              <td>{record.year ?? "–"}</td>
              <td>{record.source_title ?? "–"}</td>
              <td>{t(`docType.${record.document_type}`)}</td>
              <td className="num">{record.cited_by ?? "–"}</td>
              <td>
                {record.doi ? (
                  <a href={`https://doi.org/${record.doi}`} target="_blank" rel="noreferrer">
                    {record.doi}
                  </a>
                ) : (
                  "–"
                )}
              </td>
              {extra && <td>{extra.values[i]}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
