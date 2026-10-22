import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, exportApi, type MapExportFormat, type RecordExportFormat } from "../api";
import { downloadBlob, mapToPng, mapToSvg } from "../mapImage";
import type { NetworkOptions, ScienceMap } from "../types";

const MAP_FILES: MapExportFormat[] = ["vosviewer", "graphml", "pajek", "csv"];
const LABEL: Record<MapExportFormat, string> = {
  vosviewer: "export.vosviewer",
  graphml: "export.graphml",
  pajek: "export.pajek",
  csv: "export.csvNet",
};

interface Props {
  workspaceId: string;
  /** Present once a map has been built; image exports need its data. */
  map: ScienceMap | null;
  options: NetworkOptions;
  baseName: string;
}

export function ExportBar({ workspaceId, map, options, baseName }: Props) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("export.failed"));
    } finally {
      setBusy(null);
    }
  }

  const image = (kind: "png" | "svg") => () =>
    run(kind, async () => {
      if (!map) return;
      const blob =
        kind === "png"
          ? await mapToPng(map)
          : new Blob([mapToSvg(map)], { type: "image/svg+xml" });
      downloadBlob(blob, `${baseName}.${kind}`);
    });

  const file = (format: MapExportFormat) => () =>
    run(format, async () => {
      const { blob, filename } = await exportApi.map(workspaceId, options, format);
      downloadBlob(blob, filename);
    });

  return (
    <div className="exports">
      <h4>{t("export.map")}</h4>
      <p className="muted">{t("export.mapHelp")}</p>
      {!map && <p className="muted">{t("export.needMap")}</p>}
      <div className="actions">
        <button type="button" className="secondary" disabled={!map || !!busy} onClick={image("png")}>
          {busy === "png" ? t("export.preparing") : t("export.png")}
        </button>
        <button type="button" className="secondary" disabled={!map || !!busy} onClick={image("svg")}>
          {busy === "svg" ? t("export.preparing") : t("export.svg")}
        </button>
        {MAP_FILES.map((format) => (
          <button
            key={format}
            type="button"
            className="secondary"
            disabled={!!busy}
            onClick={file(format)}
          >
            {busy === format ? t("export.preparing") : t(LABEL[format])}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </div>
  );
}

export function DataExportBar({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<string | null>(null);
  const [includeExcluded, setIncludeExcluded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const get = (format: RecordExportFormat) => async () => {
    setBusy(format);
    setError(null);
    try {
      const { blob, filename } = await exportApi.records(workspaceId, format, includeExcluded);
      downloadBlob(blob, filename);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("export.failed"));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="exports">
      <h4>{t("export.data")}</h4>
      <p className="muted">{t("export.dataHelp")}</p>
      <div className="actions">
        <button type="button" disabled={!!busy} onClick={get("xlsx")}>
          {busy === "xlsx" ? t("export.preparing") : t("export.xlsx")}
        </button>
        <button type="button" className="secondary" disabled={!!busy} onClick={get("csv")}>
          {busy === "csv" ? t("export.preparing") : t("export.csvRecords")}
        </button>
        <label className="check">
          <input
            type="checkbox"
            checked={includeExcluded}
            onChange={(e) => setIncludeExcluded(e.target.checked)}
          />
          {t("export.includeExcluded")}
        </label>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </div>
  );
}
