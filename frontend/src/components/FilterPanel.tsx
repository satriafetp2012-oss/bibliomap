import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, workspaceApi } from "../api";
import type { DocumentType, FilterSpec, RecordPage } from "../types";
import { DataExportBar } from "./ExportBar";
import { RecordTable } from "./RecordTable";

const DOC_TYPES: DocumentType[] = [
  "article",
  "review",
  "conference_paper",
  "book_chapter",
  "book",
  "editorial",
  "letter",
  "preprint",
  "other",
];

interface Props {
  workspaceId: string;
  filters: FilterSpec;
  version: number;
  /** Totals from the workspace summary, so both tabs can show a count. */
  counts: { kept: number; excluded: number };
  onChanged: () => void;
}

const toYear = (v: string) => (v.trim() ? Number.parseInt(v, 10) || null : null);

export function FilterPanel({ workspaceId, filters, version, counts, onChanged }: Props) {
  const { t } = useTranslation();
  const [yearFrom, setYearFrom] = useState(filters.year_from?.toString() ?? "");
  const [yearTo, setYearTo] = useState(filters.year_to?.toString() ?? "");
  const [types, setTypes] = useState<DocumentType[]>(filters.document_types);
  const [languages, setLanguages] = useState(filters.languages.join(", "));
  const [minCited, setMinCited] = useState(filters.min_cited_by?.toString() ?? "");
  const [requireAbstract, setRequireAbstract] = useState(filters.require_abstract);
  const [view, setView] = useState<"kept" | "excluded">("kept");
  const [page, setPage] = useState<RecordPage | null>(null);
  const [message, setMessage] = useState<{ error: boolean; text: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    void workspaceApi.records(workspaceId, view).then((p) => !cancelled && setPage(p));
    return () => {
      cancelled = true;
    };
  }, [workspaceId, view, version]);

  async function apply(event: FormEvent) {
    event.preventDefault();
    const spec: FilterSpec = {
      year_from: toYear(yearFrom),
      year_to: toYear(yearTo),
      document_types: types,
      languages: languages
        .split(",")
        .map((l) => l.trim().toLowerCase())
        .filter(Boolean),
      min_cited_by: minCited.trim() ? Number(minCited) : null,
      require_abstract: requireAbstract,
    };
    try {
      await workspaceApi.setFilters(workspaceId, spec);
      setMessage({ error: false, text: t("filters.saved") });
      onChanged();
    } catch (e) {
      setMessage({ error: true, text: e instanceof ApiError ? e.message : t("import.errorGeneric") });
    }
  }

  const rows = page?.items ?? [];
  return (
    <section>
      <h2>{t("filters.heading")}</h2>
      <p className="muted">{t("filters.help")}</p>
      <form className="query-form" onSubmit={apply}>
        <label>
          {t("filters.yearFrom")}
          <input type="number" value={yearFrom} onChange={(e) => setYearFrom(e.target.value)} />
        </label>
        <label>
          {t("filters.yearTo")}
          <input type="number" value={yearTo} onChange={(e) => setYearTo(e.target.value)} />
        </label>
        <label>
          {t("filters.languages")}
          <input
            type="text"
            value={languages}
            placeholder="en, id"
            onChange={(e) => setLanguages(e.target.value)}
          />
        </label>
        <label>
          {t("filters.minCited")}
          <input
            type="number"
            min={0}
            value={minCited}
            onChange={(e) => setMinCited(e.target.value)}
          />
        </label>
        <fieldset className="wide">
          <legend>{t("filters.types")}</legend>
          {DOC_TYPES.map((type) => (
            <label key={type} className="check">
              <input
                type="checkbox"
                checked={types.includes(type)}
                onChange={() =>
                  setTypes((cur) =>
                    cur.includes(type) ? cur.filter((x) => x !== type) : [...cur, type],
                  )
                }
              />
              {t(`docType.${type}`)}
            </label>
          ))}
        </fieldset>
        <label className="check">
          <input
            type="checkbox"
            checked={requireAbstract}
            onChange={(e) => setRequireAbstract(e.target.checked)}
          />
          {t("filters.requireAbstract")}
        </label>
        <div className="wide">
          <button type="submit">{t("filters.apply")}</button>
          {message && (
            <span role={message.error ? "alert" : "status"} className={message.error ? "error" : "muted"}>
              {" "}
              {message.text}
            </span>
          )}
        </div>
      </form>

      <DataExportBar workspaceId={workspaceId} />

      <nav className="tabs subtabs">
        {(["kept", "excluded"] as const).map((v) => (
          <button
            key={v}
            type="button"
            className={view === v ? "tab active" : "tab"}
            aria-pressed={view === v}
            onClick={() => setView(v)}
          >
            {t(`filters.${v}`, { count: counts[v] })}
          </button>
        ))}
      </nav>
      <RecordTable
        records={rows.map((r) => r.merged.record)}
        total={page?.total}
        extra={
          view === "excluded"
            ? {
                header: t("filters.reason"),
                values: rows.map((r) =>
                  r.exclusion_reason ? t(`filters.reasons.${r.exclusion_reason}`) : "",
                ),
              }
            : {
                header: t("filters.sources"),
                values: rows.map((r) => r.merged.sources.length),
              }
        }
      />
    </section>
  );
}
