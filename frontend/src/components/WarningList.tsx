import { useTranslation } from "react-i18next";

import type { ParseWarning } from "../types";

export function WarningList({ warnings }: { warnings: ParseWarning[] }) {
  const { t } = useTranslation();
  if (warnings.length === 0) return null;
  return (
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
  );
}
