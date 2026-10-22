import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, previewImport } from "../api";
import type { ImportPreview } from "../types";
import { PreviewResult } from "./PreviewResult";

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "done"; preview: ImportPreview };

export function ImportPanel() {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>({ status: "idle" });

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setState({ status: "loading" });
    try {
      setState({ status: "done", preview: await previewImport(file) });
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
        <PreviewResult
          result={state.preview.result}
          summary={t("import.summary", {
            count: state.preview.record_count,
            filename: state.preview.filename ?? "file",
            format: t(`format.${state.preview.result.source_format}`),
          })}
        />
      )}
    </section>
  );
}
