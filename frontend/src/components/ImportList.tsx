import { useState } from "react";
import { useTranslation } from "react-i18next";

import { workspaceApi } from "../api";
import type { ImportInfo } from "../types";

interface Props {
  workspaceId: string;
  imports: ImportInfo[];
  onChanged: () => void;
}

export function ImportList({ workspaceId, imports, onChanged }: Props) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState<number | null>(null);
  const [label, setLabel] = useState("");

  async function saveLabel(importId: number) {
    if (label.trim()) await workspaceApi.renameImport(workspaceId, importId, label.trim());
    setEditing(null);
    onChanged();
  }

  async function remove(info: ImportInfo) {
    if (!window.confirm(t("import.confirmDelete", { label: info.label }))) return;
    await workspaceApi.deleteImport(workspaceId, info.id);
    onChanged();
  }

  return (
    <section>
      <h2>{t("import.listHeading")}</h2>
      {imports.length === 0 ? (
        <p className="muted">{t("import.listEmpty")}</p>
      ) : (
        <ul className="import-list">
          {imports.map((info) => (
            <li key={info.id}>
              {editing === info.id ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void saveLabel(info.id);
                  }}
                >
                  <input
                    aria-label={t("import.rename")}
                    value={label}
                    autoFocus
                    onChange={(e) => setLabel(e.target.value)}
                    onBlur={() => void saveLabel(info.id)}
                  />
                </form>
              ) : (
                <button
                  type="button"
                  className="link"
                  title={t("import.renameHint")}
                  onClick={() => {
                    setEditing(info.id);
                    setLabel(info.label);
                  }}
                >
                  {info.label}
                </button>
              )}
              <span className="muted">
                {t(`format.${info.source_format}`)} · {t("import.records", { count: info.record_count })}
              </span>
              <button type="button" className="secondary" onClick={() => void remove(info)}>
                {t("import.delete")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
