import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, workspaceApi } from "../api";
import type { ImportInfo } from "../types";
import { WarningList } from "./WarningList";

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "done"; info: ImportInfo };

interface Props {
  workspaceId: string;
  onImported: () => void;
}

export function ImportPanel({ workspaceId, onImported }: Props) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>({ status: "idle" });

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setState({ status: "loading" });
    try {
      const info = await workspaceApi.importFile(workspaceId, file);
      setState({ status: "done", info });
      onImported();
    } catch (error) {
      const message = error instanceof ApiError ? error.message : t("import.errorGeneric");
      setState({ status: "error", message });
    }
  }

  return (
    <section>
      <h2>{t("import.heading")}</h2>
      <p className="muted">{t("import.help")}</p>
      <form onSubmit={handleSubmit} className="upload">
        <label>
          {t("import.chooseFile")}
          <input
            type="file"
            accept=".txt,.csv,.ris,.nbib,.bib"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <button type="submit" disabled={!file || state.status === "loading"}>
          {t("import.submit")}
        </button>
      </form>

      {state.status === "loading" && <p role="status">{t("import.loading")}</p>}
      {state.status === "error" && (
        <p role="alert" className="error">
          {state.message}
        </p>
      )}
      {state.status === "done" && (
        <>
          <p className="summary">
            {t("import.added", {
              count: state.info.record_count,
              filename: state.info.origin ?? "file",
              format: t(`format.${state.info.source_format}`),
            })}
          </p>
          <WarningList warnings={state.info.warnings} />
        </>
      )}
    </section>
  );
}
