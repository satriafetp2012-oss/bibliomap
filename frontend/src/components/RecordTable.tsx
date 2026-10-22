import { useTranslation } from "react-i18next";

import type { BibRecord } from "../types";

// Rendering thousands of rows freezes the page; the preview only needs a sample.
const MAX_ROWS = 200;

function formatAuthors(record: BibRecord, more: string): string {
  const names = record.authors.map((a) => a.name);
  return names.length > 3 ? `${names.slice(0, 3).join("; ")} ${more}` : names.join("; ");
}

export function RecordTable({ records }: { records: BibRecord[] }) {
  const { t } = useTranslation();
  const shown = records.slice(0, MAX_ROWS);

  return (
    <div className="table-wrap">
      <p className="muted">{t("table.showing", { shown: shown.length, total: records.length })}</p>
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
