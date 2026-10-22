import { useTranslation } from "react-i18next";

import type { ParseResult } from "../types";
import { RecordTable } from "./RecordTable";

export function PreviewResult({ summary, result }: { summary: string; result: ParseResult }) {
  const { t } = useTranslation();
  const { records, warnings } = result;

  return (
    <>
      <p className="summary">{summary}</p>
      {warnings.length > 0 && (
        <details className="warnings">
          <summary>{t("import.warnings", { count: warnings.length })}</summary>
          <ul>
            {warnings.map((w, i) => (
              <li key={i}>
                {w.record_index === null
                  ? w.message
                  : t("import.warningRow", { index: w.record_index + 1, message: w.message })}
              </li>
            ))}
          </ul>
        </details>
      )}
      <RecordTable records={records} />
    </>
  );
}
